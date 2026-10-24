package com.agentworkspace.mobile.localmodels

/**
 * Sentence vectors for knowledge-base search (mobile_semantic.py), kept as int8: unit vectors
 * scaled by 127, so a passage costs [dims] bytes and a dot product of two of them divided by
 * 127² is their cosine similarity.
 */
object KnowledgeVectors {
    fun quantize(vectors: FloatArray): ByteArray = ByteArray(vectors.size) { index ->
        Math.round(vectors[index] * 127f).coerceIn(-127, 127).toByte()
    }

    /** The cosine similarity of [query] (one vector) with each vector in [matrix], in order. */
    @JvmStatic
    fun scores(query: ByteArray, matrix: ByteArray, dims: Int): FloatArray {
        require(dims > 0 && query.size == dims && matrix.size % dims == 0) { "Vector sizes do not match" }
        val count = matrix.size / dims
        val result = FloatArray(count)
        val scale = 1f / (127f * 127f)
        for (row in 0 until count) {
            var sum = 0
            val offset = row * dims
            for (index in 0 until dims) sum += query[index] * matrix[offset + index]
            result[row] = sum * scale
        }
        return result
    }
}
