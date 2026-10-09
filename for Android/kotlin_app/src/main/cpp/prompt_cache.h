#pragma once

// Prompt reuse between requests of the phone's local engine. An agent step's prompt
// extends the previous step's, so only the new tokens need evaluating; re-evaluating
// thousands of system and tool tokens every step took minutes of full CPU load on a
// phone. Qwen3.5's recurrent layers cannot forget tokens, so recurrent-state
// checkpoints taken just before the end of each prompt let a step resume where the
// next prompt starts to differ.
//
// New conversations share the opening system message (instructions and tool schemas,
// about 1,500 tokens), so its evaluated state is also saved to a file once and restored
// for later conversations, even after the engine freed its context. Free of JNI so a
// desktop test drives this same code against a real model (tests/native/prompt_cache_test.cpp).

#include <llama.h>

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <exception>
#include <new>
#include <string>
#include <vector>

namespace agent_prompt_cache {

// Each checkpoint holds every recurrent layer's state (about 19 MiB for Qwen3.5 0.8B).
// The two taken near the end of the latest prompt are the ones the next step resumes from;
// one more at the end of the system message serves the next conversation.
constexpr size_t MAX_CHECKPOINTS = 2;
constexpr size_t BATCH_TOKENS = 128;
// Shorter system messages are cheap to evaluate and not worth a file.
constexpr size_t MIN_PREFIX_TOKENS = 256;

struct Checkpoint {
    size_t n_tokens;
    std::vector<uint8_t> state;
    bool prefix = false;  // the end of the system message; kept beside the two latest
};

struct Cache {
    std::vector<llama_token> tokens;  // what the context memory holds, in order
    std::vector<Checkpoint> checkpoints;

    void clear() {
        tokens.clear();
        checkpoints.clear();
    }

    size_t checkpoint_bytes() const {
        size_t bytes = 0;
        for (const auto & checkpoint : checkpoints) bytes += checkpoint.state.size();
        return bytes;
    }
};

inline bool partial_state(const llama_model * model) {
    return llama_model_is_hybrid(model) || llama_model_is_recurrent(model);
}

/** The single token a special marker such as "<|im_start|>" encodes to, or -1. */
inline llama_token special_token(const llama_vocab * vocabulary, const std::string & text) {
    llama_token token = -1;
    return llama_tokenize(vocabulary, text.data(), static_cast<int32_t>(text.size()), &token, 1, false, true) == 1
        ? token : -1;
}

/**
 * Tokens of the opening system message (everything before the second chat message starts),
 * or 0 when there is none worth saving.
 */
inline size_t system_prefix_length(const std::vector<llama_token> & tokens, llama_token im_start) {
    if (im_start < 0 || tokens.empty() || tokens[0] != im_start) return 0;
    for (size_t i = 1; i < tokens.size(); ++i)
        if (tokens[i] == im_start) return i >= MIN_PREFIX_TOKENS ? i : 0;
    return 0;
}

/** File name for a saved prefix: the model and engine identity plus the prefix tokens (FNV-1a). */
inline std::string prefix_file_name(const std::string & identity, const std::vector<llama_token> & tokens,
                                    size_t n_tokens) {
    uint64_t hash = 1469598103934665603ULL;
    const auto mix = [&hash](const void * data, size_t size) {
        for (size_t i = 0; i < size; ++i) {
            hash ^= static_cast<const uint8_t *>(data)[i];
            hash *= 1099511628211ULL;
        }
    };
    mix(identity.data(), identity.size());
    mix(tokens.data(), n_tokens * sizeof(llama_token));
    char name[40];
    std::snprintf(name, sizeof(name), "prefix-%016llx.state", static_cast<unsigned long long>(hash));
    return name;
}

/** Saves the recurrent state after cache.tokens; a missing checkpoint only costs time later. */
inline void save_checkpoint(Cache & cache, llama_context * context, bool prefix = false) {
    try {
        const size_t size = llama_state_seq_get_size_ext(context, 0, LLAMA_STATE_SEQ_FLAGS_PARTIAL_ONLY);
        Checkpoint checkpoint{cache.tokens.size(), std::vector<uint8_t>(size), prefix};
        if (size == 0 || llama_state_seq_get_data_ext(context, checkpoint.state.data(), size, 0,
                LLAMA_STATE_SEQ_FLAGS_PARTIAL_ONLY) != size) return;
        auto & checkpoints = cache.checkpoints;
        if (prefix)
            checkpoints.erase(std::remove_if(checkpoints.begin(), checkpoints.end(),
                [](const Checkpoint & other) { return other.prefix; }), checkpoints.end());
        checkpoints.push_back(std::move(checkpoint));
        const auto latest = [&checkpoints] {
            return std::count_if(checkpoints.begin(), checkpoints.end(), [](const Checkpoint & c) { return !c.prefix; });
        };
        while (static_cast<size_t>(latest()) > MAX_CHECKPOINTS)
            checkpoints.erase(std::find_if(checkpoints.begin(), checkpoints.end(),
                [](const Checkpoint & c) { return !c.prefix; }));
    } catch (const std::bad_alloc &) {
    }
}

/**
 * Keeps the longest usable prefix of the cached sequence for `tokens` and returns its
 * length. At least one prompt token is always left to evaluate so there are fresh logits.
 */
inline size_t reuse_prefix(Cache & cache, llama_context * context, const std::vector<llama_token> & tokens,
                           bool partial) {
    if (tokens.empty()) return 0;
    auto & cached = cache.tokens;
    size_t common = 0;
    while (common < cached.size() && common < tokens.size() && cached[common] == tokens[common]) ++common;
    const size_t usable = std::min(common, tokens.size() - 1);
    llama_memory_t memory = llama_get_memory(context);
    size_t keep = 0;
    if (usable == cached.size()) {
        keep = usable;  // the new prompt extends everything in memory
    } else if (!partial) {
        if (usable > 0 && llama_memory_seq_rm(memory, 0, static_cast<llama_pos>(usable), -1)) keep = usable;
    } else {
        const Checkpoint * best = nullptr;
        for (const auto & checkpoint : cache.checkpoints)
            if (checkpoint.n_tokens > 0 && checkpoint.n_tokens <= usable &&
                (!best || checkpoint.n_tokens > best->n_tokens)) best = &checkpoint;
        // Restore the recurrent layers, then drop the attention entries after the checkpoint.
        if (best && llama_state_seq_set_data_ext(context, best->state.data(), best->state.size(), 0,
                LLAMA_STATE_SEQ_FLAGS_PARTIAL_ONLY) == best->state.size() &&
            llama_memory_seq_rm(memory, 0, static_cast<llama_pos>(best->n_tokens), -1))
            keep = best->n_tokens;
    }
    if (keep == 0) llama_memory_seq_rm(memory, 0, -1, -1);  // removing a whole sequence never fails
    cached.resize(keep);
    auto & checkpoints = cache.checkpoints;
    checkpoints.erase(std::remove_if(checkpoints.begin(), checkpoints.end(),
        [keep](const Checkpoint & checkpoint) { return checkpoint.n_tokens > keep; }), checkpoints.end());
    return keep;
}

/**
 * Restores tokens[0, n_tokens) from a saved prefix file into an otherwise empty sequence.
 * Returns false and leaves the sequence empty when the file is missing or does not match.
 */
inline bool load_prefix(Cache & cache, llama_context * context, const std::string & path,
                        const std::vector<llama_token> & tokens, size_t n_tokens) {
    if (n_tokens == 0 || n_tokens >= tokens.size()) return false;
    if (FILE * file = std::fopen(path.c_str(), "rb")) std::fclose(file);
    else return false;
    llama_memory_seq_rm(llama_get_memory(context), 0, -1, -1);
    cache.clear();
    std::vector<llama_token> stored(n_tokens);
    size_t count = 0;
    size_t read = 0;
    try {
        read = llama_state_seq_load_file(context, path.c_str(), 0, stored.data(), stored.size(), &count);
    } catch (const std::exception &) {
        read = 0;
    }
    if (read == 0 || count != n_tokens || !std::equal(stored.begin(), stored.end(), tokens.begin())) {
        llama_memory_seq_rm(llama_get_memory(context), 0, -1, -1);
        std::remove(path.c_str());  // stale or damaged; the next evaluation writes a fresh one
        return false;
    }
    cache.tokens.assign(tokens.begin(), tokens.begin() + static_cast<std::ptrdiff_t>(n_tokens));
    save_checkpoint(cache, context, true);
    return true;
}

/** Writes the sequence state after tokens[0, n_tokens) to `path` (atomically); returns success. */
inline bool save_prefix(llama_context * context, const std::string & path, const std::vector<llama_token> & tokens,
                        size_t n_tokens) {
    const std::string partial = path + ".tmp";
    bool saved = false;
    try {
        saved = llama_state_seq_save_file(context, partial.c_str(), 0, tokens.data(), n_tokens) > 0;
    } catch (const std::exception &) {
        saved = false;
    }
    if (saved) saved = std::rename(partial.c_str(), path.c_str()) == 0;
    if (!saved) std::remove(partial.c_str());
    return saved;
}

/**
 * Prepares memory for `tokens` and returns how many need no evaluation: the part already in
 * memory, or else the system message restored from `prefix_path` when that file exists.
 */
inline size_t resume(Cache & cache, llama_context * context, const std::vector<llama_token> & tokens, bool partial,
                     size_t prefix_end, const std::string & prefix_path) {
    const size_t reused = reuse_prefix(cache, context, tokens, partial);
    if (!partial || prefix_end <= reused || prefix_path.empty()) return reused;
    load_prefix(cache, context, prefix_path, tokens, prefix_end);
    return cache.tokens.size();  // unchanged when no file exists, empty after a mismatch
}

enum class Evaluation { complete, stopped, failed };

/**
 * Evaluates tokens[start, end) in batches. With a cache, evaluated tokens are recorded and,
 * for recurrent models, checkpoints are taken shortly before the end: the next step usually
 * re-tokenizes the last few prompt tokens differently ("\n\n" merges with a following "\n").
 * When `prefix_end` lies in the evaluated range, a checkpoint is also kept there and, given a
 * `prefix_path` that does not exist yet, the state is saved to it (`prefix_saved` reports it).
 * `stopped()` is polled before each batch and `evaluated(first_batch)` called after it.
 */
template <typename Stopped, typename Evaluated>
Evaluation evaluate_prompt(Cache * cache, llama_context * context, std::vector<llama_token> & tokens,
                           size_t start, bool partial, Stopped stopped, Evaluated evaluated,
                           size_t prefix_end = 0, const std::string & prefix_path = std::string(),
                           bool * prefix_saved = nullptr) {
    const size_t end = tokens.size();
    std::vector<size_t> marks;
    const bool mark_prefix = cache && partial && prefix_end > start && prefix_end < end;
    if (mark_prefix) marks.push_back(prefix_end);
    if (cache && partial)
        for (const size_t back : {size_t{4 + 64}, size_t{4}})
            if (end > back && end - back > start && end - back != prefix_end) marks.push_back(end - back);
    std::sort(marks.begin(), marks.end());
    size_t mark = 0;
    for (size_t offset = start; offset < end;) {
        if (stopped()) return Evaluation::stopped;
        size_t stop = std::min(offset + BATCH_TOKENS, end);
        if (mark < marks.size() && marks[mark] < stop) stop = marks[mark];
        auto batch = llama_batch_get_one(tokens.data() + offset, static_cast<int32_t>(stop - offset));
        if (llama_decode(context, batch) != 0) return Evaluation::failed;
        evaluated(offset == start);
        if (cache) cache->tokens.insert(cache->tokens.end(), tokens.begin() + offset, tokens.begin() + stop);
        offset = stop;
        if (mark < marks.size() && marks[mark] == stop) {
            const bool at_prefix = mark_prefix && stop == prefix_end;
            save_checkpoint(*cache, context, at_prefix);
            if (at_prefix && !prefix_path.empty()) {
                FILE * existing = std::fopen(prefix_path.c_str(), "rb");
                if (existing) std::fclose(existing);
                else if (save_prefix(context, prefix_path, tokens, prefix_end) && prefix_saved) *prefix_saved = true;
            }
            ++mark;
        }
    }
    return Evaluation::complete;
}

}  // namespace agent_prompt_cache
