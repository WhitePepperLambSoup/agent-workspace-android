#include <jni.h>
#include <android/log.h>
#include <llama.h>
#include <mtmd.h>
#include <mtmd-helper.h>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <deque>
#include <fcntl.h>
#include <memory>
#include <mutex>
#include <regex>
#include <stdexcept>
#include <string>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>

namespace {
using json = nlohmann::json;
using Clock = std::chrono::steady_clock;
constexpr size_t MAX_REQUEST_BYTES = 8 * 1024 * 1024;
constexpr size_t MAX_PROMPT_BYTES = 4 * 1024 * 1024;
constexpr size_t MAX_TOKENIZER_PROMPT_BYTES = 32 * 1024 * 1024;
constexpr size_t MAX_TOKENIZER_REQUEST_BYTES = 64 * 1024 * 1024;
constexpr size_t MAX_OUTPUT_BYTES = 256 * 1024;
constexpr size_t MAX_IMAGES = 4;
constexpr size_t MAX_RGB_IMAGE_BYTES = 512 * 512 * 3;
std::mutex engine_mutex;
std::mutex state_mutex;
std::once_flag backend_once;
std::atomic<bool> cancelled{false};
std::deque<std::string> pending_cancellations;
std::string model_root;
std::string loaded_id;
std::string active_request;
std::string generation_phase;
std::string last_error;
json last_generation = nullptr;
bool initialized = false;
bool generating = false;
int context_size = 0;
std::unique_ptr<llama_model, decltype(&llama_model_free)> model{nullptr, llama_model_free};
std::unique_ptr<FILE, decltype(&fclose)> model_file{nullptr, fclose};
struct stat loaded_stat{};
std::unique_ptr<llama_model, decltype(&llama_model_free)> vocabulary_model{nullptr, llama_model_free};
std::string vocabulary_id;
struct stat vocabulary_stat{};

struct RequestFailure : std::runtime_error {
    std::string code;
    RequestFailure(std::string code_, const char * message)
        : std::runtime_error(message), code(std::move(code_)) {}
};

bool supported_model_id(const std::string & id) {
    return id == "qwen3-0.6b-q4-k-m" || id == "qwen3-1.7b-q4-k-m" ||
        id == "qwen3-0.6b-q8-0" || id == "qwen3-1.7b-q8-0" ||
        id == "qwen3.5-0.8b-q4-k-m" || id == "qwen3.5-0.8b-q8-0" ||
        id == "qwen3.5-2b-q4-k-m" || id == "qwen3.5-2b-q8-0" ||
        id == "qwen3.5-0.8b-agent-v1-q4-k-m" ||
        id == "qwen3.5-0.8b-agent-v2-q4-k-m" ||
        id == "qwen3.5-0.8b-agent-v3-q4-k-m";
}

std::string dump(const json & value) {
    // A finite token budget can end inside a UTF-8 code point.
    return value.dump(-1, ' ', false, json::error_handler_t::replace);
}

json failure(const char * code, const char * message) {
    std::lock_guard<std::mutex> lock(state_mutex);
    last_error = code;
    return { {"error", {{"code", code}, {"message", message}}} };
}

void quiet_log(ggml_log_level level, const char * text, void *) {
    if (level == GGML_LOG_LEVEL_ERROR) __android_log_write(ANDROID_LOG_ERROR, "AgentQwen", text);
}

struct Budget {
    Clock::time_point deadline;
    bool stopped() const { return cancelled.load() || Clock::now() >= deadline; }
};
bool abort_decode(void * pointer) { return static_cast<Budget *>(pointer)->stopped(); }
bool progress_load(float, void * pointer) { return !static_cast<Budget *>(pointer)->stopped(); }
void set_generation_phase(const char * phase);
bool observe_image_node(ggml_tensor *, bool ask, void * pointer) {
    // Observe CPU encoder nodes so cancellation can stop between nodes.
    if (!ask) set_generation_phase("image_encoding_active");
    return ask || !static_cast<Budget *>(pointer)->stopped();
}

struct RunState {
    explicit RunState(const std::string & id, int n_context) {
        std::lock_guard<std::mutex> lock(state_mutex);
        auto pending = std::find(pending_cancellations.begin(), pending_cancellations.end(), id);
        cancelled.store(pending != pending_cancellations.end());
        if (pending != pending_cancellations.end()) pending_cancellations.erase(pending);
        active_request = id;
        generating = true;
        generation_phase = "loading_model";
        context_size = n_context;
        last_error.clear();
    }
    ~RunState() {
        std::lock_guard<std::mutex> lock(state_mutex);
        generating = false;
        generation_phase.clear();
        active_request.clear();
        context_size = 0;
    }
};

void set_generation_phase(const char * phase) {
    std::lock_guard<std::mutex> lock(state_mutex);
    generation_phase = phase;
}

void free_model() {
    vocabulary_model.reset();
    vocabulary_id.clear();
    vocabulary_stat = {};
    model.reset();
    model_file.reset();
    std::lock_guard<std::mutex> lock(state_mutex);
    loaded_id.clear();
    loaded_stat = {};
}

std::string required_text(const json & request, const char * key, size_t limit) {
    if (!request.contains(key) || !request[key].is_string())
        throw RequestFailure("invalid_request", "Missing or invalid native request string");
    auto value = request[key].get<std::string>();
    if (value.empty() || value.size() > limit)
        throw RequestFailure("invalid_request", "Native request string exceeded its limit");
    return value;
}

int required_int(const json & request, const char * key, int lower, int upper) {
    if (!request.contains(key) || !request[key].is_number_integer())
        throw RequestFailure("invalid_request", "Missing or invalid native request integer");
    const int64_t value = request[key].get<int64_t>();
    if (value < lower || value > upper)
        throw RequestFailure("invalid_request", "Native request integer exceeded phone limits");
    return static_cast<int>(value);
}

FILE * open_private_model(const std::string & id, const std::string & path, struct stat & info) {
    const std::string expected = model_root + "/" + id + "/model.gguf";
    if (path != expected || path.find('\0') != std::string::npos)
        throw RequestFailure("invalid_model_path", "Local Qwen model must be in private model storage");
    const int root_fd = open(model_root.c_str(), O_RDONLY | O_CLOEXEC | O_DIRECTORY | O_NOFOLLOW);
    if (root_fd < 0) throw RequestFailure("model_not_installed", "Private model storage is unavailable");
    const int directory_fd = openat(root_fd, id.c_str(), O_RDONLY | O_CLOEXEC | O_DIRECTORY | O_NOFOLLOW);
    close(root_fd);
    if (directory_fd < 0) throw RequestFailure("model_not_installed", "Selected local Qwen model is not installed");
    const int fd = openat(directory_fd, "model.gguf", O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    close(directory_fd);
    if (fd < 0) throw RequestFailure("model_not_installed", "Selected local Qwen model is not installed");
    if (fstat(fd, &info) != 0 || !S_ISREG(info.st_mode) || info.st_size < 16 ||
        info.st_size > 3LL * 1024 * 1024 * 1024) {
        close(fd);
        throw RequestFailure("invalid_model_file", "Local Qwen model is not a bounded regular GGUF file");
    }
    FILE * file = fdopen(fd, "rb");
    if (!file) {
        close(fd);
        throw RequestFailure("invalid_model_file", "Local Qwen model could not be opened");
    }
    char magic[4];
    const bool valid = fread(magic, 1, 4, file) == 4 && std::string(magic, 4) == "GGUF";
    rewind(file);
    if (!valid) {
        fclose(file);
        throw RequestFailure("invalid_model_file", "Local Qwen model has an invalid GGUF header");
    }
    return file;
}

json generation_result(json metadata, const std::string & text, int prompt_tokens, int output_tokens,
                       const char * finish, bool was_cancelled, int64_t first_token_ms, int64_t elapsed_ms) {
    const int64_t decode_ms = first_token_ms >= 0 ? elapsed_ms - first_token_ms : 0;
    metadata.update({
        {"prompt_tokens", prompt_tokens}, {"generated_tokens", output_tokens}, {"finish_reason", finish},
        {"first_token_ms", first_token_ms >= 0 ? json(first_token_ms) : json(nullptr)},
        {"elapsed_ms", elapsed_ms},
        {"tokens_per_second", output_tokens > 1 && decode_ms > 0
            ? json((output_tokens - 1) * 1000.0 / decode_ms) : json(nullptr)},
        {"completed_at", std::chrono::duration<double>(
            std::chrono::system_clock::now().time_since_epoch()).count()}
    });
    {
        std::lock_guard<std::mutex> lock(state_mutex);
        last_generation = metadata;
    }
    return {{"text", text}, {"prompt_tokens", prompt_tokens}, {"generated_tokens", output_tokens},
            {"image_count", metadata.value("image_count", size_t{0})},
            {"image_tokens", metadata.value("image_tokens", size_t{0})},
            {"finish_reason", finish}, {"cancelled", was_cancelled},
            {"first_token_ms", first_token_ms}, {"elapsed_ms", elapsed_ms}};
}

json interrupted(const std::string & text = "", int prompt_tokens = 0, int output_tokens = 0,
                 const json & metadata = json::object(), int64_t first_token_ms = -1, int64_t elapsed_ms = 0) {
    const bool was_cancelled = cancelled.load();
    // A deadline may interrupt a tool-call envelope. Return its usage and
    // diagnostics, but never offer partial output as an executable completion.
    auto result = generation_result(metadata, was_cancelled ? text : "", prompt_tokens, output_tokens,
        was_cancelled ? "cancelled" : "timeout", was_cancelled, first_token_ms, elapsed_ms);
    if (!was_cancelled)
        result.update(failure("generation_timeout", "Local Qwen reached its finite generation time limit"));
    return result;
}

json generate(const std::string & raw, const std::vector<std::string> & rgb_images) {
    std::unique_lock<std::mutex> engine_lock(engine_mutex, std::try_to_lock);
    if (!engine_lock.owns_lock())
        return failure("engine_busy", "Another local Qwen generation or unload is running");
    try {
        if (!initialized) return failure("engine_unavailable", "Native inference has not been initialized");
        if (raw.size() > MAX_REQUEST_BYTES) throw RequestFailure("invalid_request", "Native request is too large");
        auto request = json::parse(raw, [](int depth, json::parse_event_t, json &) {
            if (depth > 32) throw RequestFailure("invalid_request", "Native request JSON is too deeply nested");
            return true;
        });
        if (!request.is_object()) throw RequestFailure("invalid_request", "Native request must be a JSON object");
        required_int(request, "version", 1, 1);
        const auto id = required_text(request, "model_id", 64);
        if (!supported_model_id(id))
            throw RequestFailure("invalid_request", "Unsupported small Qwen model ID");
        const auto request_id = required_text(request, "request_id", 80);
        if (!std::regex_match(request_id, std::regex("[A-Za-z0-9_-]{1,80}")))
            throw RequestFailure("invalid_request", "Invalid native inference request ID");
        const auto path = required_text(request, "model_path", 4096);
        const auto prompt = required_text(request, "prompt", MAX_PROMPT_BYTES);
        const int model_context_limit = id.rfind("qwen3.5-", 0) == 0 ? 262144 : 32768;
        const int n_context = required_int(request, "context_size", 512, model_context_limit);
        const int n_predict = required_int(request, "max_output_tokens", 1, 8192);
        const std::string memory_mode = request.contains("memory_mode")
            ? required_text(request, "memory_mode", 16) : "balanced";
        if (memory_mode != "balanced" && memory_mode != "extended")
            throw RequestFailure("invalid_request", "Invalid local memory mode");
        if (n_predict >= n_context)
            return failure("context_exceeded", "Local output allowance leaves no room for the prompt");
        const int n_threads = required_int(request, "threads", 1, 64);
        const int timeout = required_int(request, "generation_timeout_ms", 1, 7200000);
        if (rgb_images.size() > MAX_IMAGES)
            throw RequestFailure("invalid_image", "Attach at most four local images");
        if (request.contains("images") && (!request["images"].is_array() ||
            request["images"].size() != rgb_images.size()))
            throw RequestFailure("invalid_image", "Local image metadata does not match RGB input");
        if (!rgb_images.empty() && (id.rfind("qwen3.5-", 0) != 0 || !request.contains("images")))
            throw RequestFailure("unsupported_vision", "Select Qwen3.5 to read local images");
        if (!request.contains("temperature") || !request["temperature"].is_number())
            throw RequestFailure("invalid_request", "Invalid native inference temperature");
        const float temperature = request["temperature"].get<float>();
        if (!std::isfinite(temperature) || temperature < 0 || temperature > 2)
            throw RequestFailure("invalid_request", "Native temperature exceeded its finite limit");

        const auto started = Clock::now();
        Budget budget{started + std::chrono::milliseconds(timeout)};
        RunState state(request_id, n_context);
        int n_prompt = 0;
        int generated = 0;
        int64_t first_token_ms = -1;
        std::string text;
        json generation_metadata = {
            {"model_id", id}, {"request_id", request_id}, {"context_size", n_context},
            {"actual_context_size", nullptr}, {"threads", n_threads}, {"memory_mode", memory_mode},
            {"generation_timeout_ms", timeout}, {"image_count", rgb_images.size()},
            {"image_tokens", 0}, {"projection_id", nullptr}
        };
        const auto interrupt = [&]() {
            return interrupted(text, n_prompt, generated, generation_metadata, first_token_ms,
                std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - started).count());
        };
        if (budget.stopped()) return interrupt();
        struct stat info{};
        std::unique_ptr<FILE, decltype(&fclose)> file(open_private_model(id, path, info), fclose);
        if (!model || loaded_id != id || loaded_stat.st_dev != info.st_dev ||
            loaded_stat.st_ino != info.st_ino || loaded_stat.st_size != info.st_size ||
            loaded_stat.st_mtime != info.st_mtime) {
            free_model();
            llama_model_params params = llama_model_default_params();
            params.n_gpu_layers = 0;
            params.load_mode = LLAMA_LOAD_MODE_MMAP;
            params.progress_callback = progress_load;
            params.progress_callback_user_data = &budget;
            model.reset(llama_model_load_from_file_ptr(file.get(), params));
            if (!model) return budget.stopped() ? interrupt() :
                failure("model_load_failed", "llama.cpp could not load the installed Qwen GGUF model");
            char architecture[64]{};
            llama_model_meta_val_str(model.get(), "general.architecture", architecture, sizeof(architecture));
            const std::string expected_arch = id.rfind("qwen3.5-", 0) == 0 ? "qwen35" : "qwen3";
            if (std::string(architecture) != expected_arch || llama_model_n_params(model.get()) > 2750000000ULL) {
                free_model();
                return failure("unsupported_model", "This CPU engine accepts only verified small Qwen3 or Qwen3.5 models");
            }
            model_file = std::move(file);
            std::lock_guard<std::mutex> lock(state_mutex);
            loaded_id = id;
            loaded_stat = info;
        }
        const int trained_context = llama_model_n_ctx_train(model.get());
        if (trained_context <= 0 || n_context > trained_context)
            return failure("context_exceeded", "Selected context exceeds the installed model context metadata");
        if (budget.stopped()) return interrupt();
        set_generation_phase("tokenizing");
        const llama_vocab * vocabulary = llama_model_get_vocab(model.get());
        std::vector<llama_token> tokens;
        mtmd::context_ptr vision;
        mtmd::input_chunks_ptr chunks;
        std::vector<mtmd::bitmap_ptr> bitmaps;
        std::unique_ptr<FILE, decltype(&fclose)> projection_file{nullptr, fclose};
        std::string projection_id;
        size_t image_tokens = 0;
        if (!rgb_images.empty()) {
            projection_id = id.rfind("qwen3.5-2b-", 0) == 0
                ? "qwen3.5-2b-vision-f16" : "qwen3.5-0.8b-vision-f16";
            generation_metadata["projection_id"] = projection_id;
            const auto projection_path = required_text(request, "projection_path", 4096);
            struct stat projection_info{};
            projection_file.reset(open_private_model(projection_id, projection_path, projection_info));
            const int64_t expected_bytes = id.rfind("qwen3.5-2b-", 0) == 0 ? 668227264LL : 204987232LL;
            if (projection_info.st_size != expected_bytes)
                return failure("invalid_projection_file", "The local vision projection has the wrong pinned size");
            auto vision_params = mtmd_context_params_default();
            vision_params.use_gpu = false;
            vision_params.n_threads = n_threads;
            vision_params.warmup = false;
            vision_params.print_timings = false;
            vision_params.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_DISABLED;
            vision_params.image_min_tokens = 64;
            vision_params.image_max_tokens = 256;
            vision_params.cb_eval = observe_image_node;
            vision_params.cb_eval_user_data = &budget;
            vision_params.progress_callback = progress_load;
            vision_params.progress_callback_user_data = &budget;
            // Load the already-opened no-symlink descriptor. A path replacement
            // cannot redirect the projector between validation and loading.
            const auto descriptor_path = "/proc/self/fd/" + std::to_string(fileno(projection_file.get()));
            set_generation_phase("loading_projection");
            vision.reset(mtmd_init_from_file(descriptor_path.c_str(), model.get(), vision_params));
            if (!vision || !mtmd_support_vision(vision.get()))
                return budget.stopped() ? interrupt() : failure("projection_load_failed",
                    "llama.cpp could not load the matching local Qwen vision projection");
            if (budget.stopped()) return interrupt();
            std::vector<const mtmd_bitmap *> bitmap_pointers;
            for (size_t i = 0; i < rgb_images.size(); ++i) {
                const auto & metadata = request["images"][i];
                const int width = required_int(metadata, "width", 1, 512);
                const int height = required_int(metadata, "height", 1, 512);
                if (rgb_images[i].size() != static_cast<size_t>(width * height * 3))
                    throw RequestFailure("invalid_image", "Local RGB image dimensions are inconsistent");
                bitmaps.emplace_back(mtmd_bitmap_init(width, height,
                    reinterpret_cast<const unsigned char *>(rgb_images[i].data())));
                if (!bitmaps.back()) return failure("invalid_image", "Local image bitmap allocation failed");
                bitmap_pointers.push_back(bitmaps.back().get());
            }
            chunks.reset(mtmd_input_chunks_init());
            const mtmd_input_text input{prompt.data(), prompt.size(), false, true};
            set_generation_phase("tokenizing_images");
            if (mtmd_tokenize(vision.get(), chunks.get(), &input, bitmap_pointers.data(),
                bitmap_pointers.size()) != 0)
                return failure("invalid_image", "Local images could not be matched to the chat prompt");
            const size_t needed = mtmd_helper_get_n_tokens(chunks.get());
            if (needed == 0 || needed + n_predict > static_cast<size_t>(n_context))
                return failure("context_exceeded", "Local text and image tokens plus output exceed the phone context");
            n_prompt = static_cast<int>(needed);
            for (size_t i = 0; i < mtmd_input_chunks_size(chunks.get()); ++i) {
                const auto chunk = mtmd_input_chunks_get(chunks.get(), i);
                if (mtmd_input_chunk_get_type(chunk) == MTMD_INPUT_CHUNK_TYPE_IMAGE)
                    image_tokens += mtmd_input_chunk_get_n_tokens(chunk);
            }
            if (image_tokens == 0 || image_tokens > rgb_images.size() * 256)
                return failure("invalid_image", "Local vision tokens exceeded the bounded image allowance");
            generation_metadata["image_tokens"] = image_tokens;
        } else {
            const int needed = -llama_tokenize(vocabulary, prompt.data(), static_cast<int32_t>(prompt.size()),
                                              nullptr, 0, false, true);
            if (needed <= 0 || needed + n_predict > n_context)
                return failure("context_exceeded", "Local Qwen prompt plus output exceeds the bounded phone context");
            tokens.resize(needed);
            n_prompt = llama_tokenize(vocabulary, prompt.data(), static_cast<int32_t>(prompt.size()),
                                     tokens.data(), needed, false, true);
            if (n_prompt != needed) return failure("tokenization_failed", "Local Qwen prompt tokenization failed");
        }

        llama_context_params params = llama_context_default_params();
        params.n_ctx = n_context;
        params.n_batch = 128;
        params.n_ubatch = 64;
        params.n_seq_max = 1;
        params.n_threads = n_threads;
        params.n_threads_batch = n_threads;
        params.type_k = GGML_TYPE_F16;
        params.type_v = GGML_TYPE_F16;
        params.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_DISABLED;
        params.offload_kqv = false;
        params.op_offload = false;
        params.abort_callback = abort_decode;
        params.abort_callback_data = &budget;
        set_generation_phase("allocating_context");
        std::unique_ptr<llama_context, decltype(&llama_free)> context(
            llama_init_from_model(model.get(), params), llama_free);
        if (!context) return budget.stopped() ? interrupt() :
            failure("insufficient_memory", "Not enough free memory to allocate local Qwen context");
        generation_metadata["actual_context_size"] = llama_n_ctx(context.get());
        auto sampling = llama_sampler_chain_default_params();
        std::unique_ptr<llama_sampler, decltype(&llama_sampler_free)> sampler(
            llama_sampler_chain_init(sampling), llama_sampler_free);
        if (temperature <= 0) {
            llama_sampler_chain_add(sampler.get(), llama_sampler_init_greedy());
        } else {
            llama_sampler_chain_add(sampler.get(), llama_sampler_init_top_k(20));
            llama_sampler_chain_add(sampler.get(), llama_sampler_init_top_p(0.8f, 1));
            llama_sampler_chain_add(sampler.get(), llama_sampler_init_temp(temperature));
            llama_sampler_chain_add(sampler.get(), llama_sampler_init_dist(LLAMA_DEFAULT_SEED));
        }
        const auto prompt_started = Clock::now();
        if (vision) {
            llama_pos n_past = 0;
            for (size_t i = 0; i < mtmd_input_chunks_size(chunks.get()); ++i) {
                if (budget.stopped()) return interrupt();
                const auto chunk = mtmd_input_chunks_get(chunks.get(), i);
                const bool image = mtmd_input_chunk_get_type(chunk) == MTMD_INPUT_CHUNK_TYPE_IMAGE;
                int32_t evaluated = 0;
                if (image) {
                    set_generation_phase("image_encoding");
                    evaluated = mtmd_encode_chunk(vision.get(), chunk);
                    // The pinned scheduler returns success after an observer
                    // stops graph evaluation. Check our own budget before
                    // reading or decoding its incomplete image embeddings.
                    if (budget.stopped()) return interrupt();
                    if (evaluated == 0) evaluated = mtmd_helper_decode_image_chunk(vision.get(),
                        context.get(), chunk, mtmd_get_output_embd(vision.get()), n_past, 0, 128,
                        &n_past, nullptr, nullptr);
                } else {
                    evaluated = mtmd_helper_eval_chunk_single(vision.get(), context.get(), chunk,
                        n_past, 0, 128, i + 1 == mtmd_input_chunks_size(chunks.get()), &n_past);
                }
                if (evaluated != 0)
                    return budget.stopped() ? interrupt() :
                        failure("decode_failed", "Local text or image evaluation failed");
                if (budget.stopped()) return interrupt();
                set_generation_phase(image ? "image_evaluation" : "prompt_evaluation");
            }
        } else {
            for (int offset = 0; offset < n_prompt; offset += 128) {
                if (budget.stopped()) return interrupt();
                auto batch = llama_batch_get_one(tokens.data() + offset, std::min(128, n_prompt - offset));
                if (llama_decode(context.get(), batch) != 0) return budget.stopped() ? interrupt() :
                    failure("decode_failed", "Local Qwen prompt evaluation failed");
                // This phase proves at least one real CPU prompt batch completed.
                if (offset == 0) set_generation_phase("prompt_evaluation");
            }
        }
        const int64_t prompt_ms = std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - prompt_started).count();
        generation_metadata["prompt_evaluation_ms"] = prompt_ms;
        generation_metadata["prompt_tokens_per_second"] = prompt_ms > 0 ? json(n_prompt * 1000.0 / prompt_ms) : json(nullptr);
        std::string finish = "length";
        while (generated < n_predict) {
            if (budget.stopped()) return interrupt();
            llama_token token = llama_sampler_sample(sampler.get(), context.get(), -1);
            if (llama_vocab_is_eog(vocabulary, token)) { finish = "stop"; break; }
            char piece[256];
            int length = llama_token_to_piece(vocabulary, token, piece, sizeof(piece), 0, true);
            if (length < 0) {
                if (-length > 65536) return failure("decode_failed", "Local Qwen returned an oversized token");
                std::vector<char> buffer(-length);
                length = llama_token_to_piece(vocabulary, token, buffer.data(), buffer.size(), 0, true);
                if (length < 0) return failure("decode_failed", "Local Qwen token decoding failed");
                text.append(buffer.data(), length);
            } else {
                text.append(piece, length);
            }
            ++generated;
            if (first_token_ms < 0) first_token_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                Clock::now() - started).count();
            if (text.size() >= MAX_OUTPUT_BYTES) { finish = "length"; break; }
            if (generated < n_predict) {
                auto batch = llama_batch_get_one(&token, 1);
                if (llama_decode(context.get(), batch) != 0) return budget.stopped() ?
                    interrupt() : failure("decode_failed", "Local Qwen token evaluation failed");
                if (generated == 1) set_generation_phase("token_generation");
            }
        }
        const int64_t elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - started).count();
        return generation_result(generation_metadata, text, n_prompt, generated,
            finish.c_str(), false, first_token_ms, elapsed);
    } catch (const RequestFailure & error) {
        return failure(error.code.c_str(), error.what());
    } catch (const std::bad_alloc &) {
        return failure("insufficient_memory", "Not enough free memory for local Qwen inference");
    } catch (const std::exception &) {
        return failure("native_error", "Local Qwen request parsing or native inference failed");
    }
}

std::string bytes(JNIEnv * env, jbyteArray input, size_t limit) {
    if (!input) throw RequestFailure("invalid_request", "Native request is missing");
    const jsize size = env->GetArrayLength(input);
    if (size < 0 || static_cast<size_t>(size) > limit)
        throw RequestFailure("invalid_request", "Native request exceeds its byte limit");
    std::string value(size, '\0');
    if (size) env->GetByteArrayRegion(input, 0, size, reinterpret_cast<jbyte *>(value.data()));
    return value;
}

jbyteArray result(JNIEnv * env, const json & value) {
    const std::string text = dump(value);
    jbyteArray array = env->NewByteArray(static_cast<jsize>(text.size()));
    if (array && !text.empty()) env->SetByteArrayRegion(array, 0, text.size(),
        reinterpret_cast<const jbyte *>(text.data()));
    return array;
}
} // namespace

extern "C" JNIEXPORT jbyteArray JNICALL
Java_com_agentworkspace_mobile_localmodels_LocalModelBridge_nativeInitialize(
    JNIEnv * env, jobject, jbyteArray root) {
    try {
        const std::string path = bytes(env, root, 4096);
        char * canonical = realpath(path.c_str(), nullptr);
        const bool valid = canonical && path == canonical && path.size() > 24 &&
            path.substr(path.size() - 24) == "/agent-data/local-models";
        free(canonical);
        if (!valid) return result(env, failure("invalid_model_path", "Invalid private model root"));
        std::lock_guard<std::mutex> lock(engine_mutex);
        std::call_once(backend_once, [] {
            llama_log_set(quiet_log, nullptr);
            mtmd_helper_log_set(quiet_log, nullptr);
            llama_backend_init();
        });
        if (initialized && model_root != path) free_model();
        { std::lock_guard<std::mutex> state_lock(state_mutex);
          model_root = path; initialized = true; last_error.clear(); }
        return result(env, json{{"initialized", true}});
    } catch (const std::exception &) {
        return result(env, failure("engine_unavailable", "Native inference initialization failed"));
    }
}

extern "C" JNIEXPORT jbyteArray JNICALL
Java_com_agentworkspace_mobile_localmodels_LocalModelBridge_nativeStatus(JNIEnv * env, jobject) {
    std::lock_guard<std::mutex> lock(state_mutex);
    return result(env, json{{"available", initialized}, {"engine", "llama.cpp"},
        {"engine_revision", AGENT_LLAMA_REVISION}, {"model_root", model_root},
        {"loaded_model", loaded_id.empty() ? json(nullptr) : json(loaded_id)},
        {"generating", generating}, {"context_size", context_size},
        {"supports_vision", true}, {"max_images", MAX_IMAGES}, {"image_max_tokens", 256},
        {"generation_phase", generation_phase.empty() ? json(nullptr) : json(generation_phase)},
        {"last_generation", last_generation},
        {"last_error", last_error.empty() ? json(nullptr) : json(last_error)}});
}

extern "C" JNIEXPORT jbyteArray JNICALL
Java_com_agentworkspace_mobile_localmodels_LocalModelBridge_nativeCountPromptTokens(
    JNIEnv * env, jobject, jbyteArray input) {
    std::unique_lock<std::mutex> lock(engine_mutex, std::try_to_lock);
    if (!lock.owns_lock()) return result(env, failure("engine_busy", "Local engine is busy; tokenizer did not interrupt it"));
    try {
        if (!initialized) return result(env, failure("engine_unavailable", "Native tokenizer is unavailable"));
        const auto request = json::parse(bytes(env, input, MAX_TOKENIZER_REQUEST_BYTES));
        const auto id = required_text(request, "model_id", 64);
        if (!supported_model_id(id)) throw RequestFailure("invalid_request", "Unsupported tokenizer model ID");
        const auto path = required_text(request, "model_path", 4096);
        const auto prompt = required_text(request, "prompt", MAX_TOKENIZER_PROMPT_BYTES);
        struct stat info{};
        std::unique_ptr<FILE, decltype(&fclose)> file(open_private_model(id, path, info), fclose);
        const auto same_file = [&info](const struct stat & previous) {
            return previous.st_dev == info.st_dev && previous.st_ino == info.st_ino &&
                previous.st_size == info.st_size && previous.st_mtime == info.st_mtime &&
                previous.st_ctime == info.st_ctime;
        };
        llama_model * source = nullptr;
        if (model && loaded_id == id && same_file(loaded_stat)) source = model.get();
        else {
            if (!vocabulary_model || vocabulary_id != id || !same_file(vocabulary_stat)) {
                vocabulary_model.reset();
                vocabulary_id.clear();
                auto params = llama_model_default_params();
                params.vocab_only = true;
                params.n_gpu_layers = 0;
                params.load_mode = LLAMA_LOAD_MODE_MMAP;
                vocabulary_model.reset(llama_model_load_from_file_ptr(file.get(), params));
                if (!vocabulary_model) return result(env, failure("tokenization_failed", "Could not load the installed GGUF vocabulary"));
                vocabulary_id = id;
                vocabulary_stat = info;
            }
            source = vocabulary_model.get();
        }
        const auto * vocab = llama_model_get_vocab(source);
        const int count = -llama_tokenize(vocab, prompt.data(), static_cast<int32_t>(prompt.size()), nullptr, 0, false, true);
        if (count <= 0) return result(env, failure("tokenization_failed", "Local prompt tokenization failed"));
        return result(env, json{{"model_id", id}, {"prompt_tokens", count},
            {"model_max_context_tokens", llama_model_n_ctx_train(source)},
            {"count_source", "installed_gguf_vocabulary"}, {"includes_image_tokens", false}});
    } catch (const RequestFailure & failure_) { return result(env, failure(failure_.code.c_str(), failure_.what())); }
    catch (const std::bad_alloc &) { return result(env, failure("insufficient_memory", "Local tokenizer allocation failed")); }
    catch (const std::exception &) { return result(env, failure("tokenization_failed", "Local tokenizer request failed")); }
}

extern "C" JNIEXPORT jbyteArray JNICALL
Java_com_agentworkspace_mobile_localmodels_LocalModelBridge_nativeGenerate(
    JNIEnv * env, jobject, jbyteArray request, jobjectArray images) {
    try {
        const jsize count = images ? env->GetArrayLength(images) : 0;
        if (count < 0 || static_cast<size_t>(count) > MAX_IMAGES)
            throw RequestFailure("invalid_image", "Local image count exceeds the phone limit");
        std::vector<std::string> rgb_images;
        for (jsize i = 0; i < count; ++i) {
            auto image = static_cast<jbyteArray>(env->GetObjectArrayElement(images, i));
            rgb_images.push_back(bytes(env, image, MAX_RGB_IMAGE_BYTES));
            env->DeleteLocalRef(image);
        }
        return result(env, generate(bytes(env, request, MAX_REQUEST_BYTES), rgb_images));
    }
    catch (const RequestFailure & error) { return result(env, failure(error.code.c_str(), error.what())); }
    catch (const std::exception &) { return result(env, failure("invalid_request", "Native request is invalid")); }
}

extern "C" JNIEXPORT void JNICALL
Java_com_agentworkspace_mobile_localmodels_LocalModelBridge_nativeCancel(
    JNIEnv * env, jobject, jbyteArray request) {
    try {
        const std::string id = bytes(env, request, 80);
        std::lock_guard<std::mutex> lock(state_mutex);
        if (id.empty() || active_request == id) cancelled.store(true);
        else {
            if (std::find(pending_cancellations.begin(), pending_cancellations.end(), id) == pending_cancellations.end())
                pending_cancellations.push_back(id);
            if (pending_cancellations.size() > 64) pending_cancellations.pop_front();
        }
    } catch (const std::exception &) { /* Invalid cancellation IDs cannot enter the queue. */ }
}

extern "C" JNIEXPORT void JNICALL
Java_com_agentworkspace_mobile_localmodels_LocalModelBridge_nativeUnload(JNIEnv *, jobject) {
    cancelled.store(true);
    std::lock_guard<std::mutex> lock(engine_mutex);
    free_model();
}
