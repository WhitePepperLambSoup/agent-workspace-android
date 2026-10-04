cmake_minimum_required(VERSION 3.22)
project(agent_qwen LANGUAGES C CXX)

include(FetchContent)
# Quantized CPU inference is unusably slow with Android's unoptimized Debug
# flags. Keep debug symbols and diagnostics, while compiling every native
# subdirectory (llama/ggml and this JNI bridge) with the optimized CPU kernels.
# No fast-math or CPU features beyond the portable ABI baseline are enabled.
add_compile_options(-O3)
set(AGENT_LLAMA_REVISION "7fe450e19305b828c199d602c23a8337aaa1f03b")
set(AGENT_LLAMA_ARCHIVE
    "https://codeload.github.com/ggml-org/llama.cpp/tar.gz/${AGENT_LLAMA_REVISION}"
    CACHE STRING "Pinned llama.cpp source archive or local copy of that archive")

# Only the portable CPU library is included. No server, subprocess, network,
# optional GPU library, or runtime-selected backend is built into this APK.
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_IS_DEV OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_COMMON OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TOOLS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_SERVER OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_MTMD ON CACHE BOOL "" FORCE)
set(MTMD_VIDEO OFF CACHE BOOL "" FORCE)
set(LLAMA_OPENSSL OFF CACHE BOOL "" FORCE)
set(LLAMA_SUBPROCESS OFF CACHE BOOL "" FORCE)
set(GGML_BACKEND_DL OFF CACHE BOOL "" FORCE)
set(GGML_NATIVE OFF CACHE BOOL "" FORCE)
set(GGML_OPENMP OFF CACHE BOOL "" FORCE)
set(GGML_BLAS OFF CACHE BOOL "" FORCE)
set(GGML_LLAMAFILE OFF CACHE BOOL "" FORCE)
set(GGML_CPU_REPACK OFF CACHE BOOL "" FORCE)
set(GGML_CPU_KLEIDIAI OFF CACHE BOOL "" FORCE)
set(GGML_VULKAN OFF CACHE BOOL "" FORCE)
set(GGML_CUDA OFF CACHE BOOL "" FORCE)
set(GGML_METAL OFF CACHE BOOL "" FORCE)
set(GGML_SYCL OFF CACHE BOOL "" FORCE)
foreach(feature SSE42 AVX AVX2 BMI2 FMA F16C AVX512)
    set(GGML_${feature} OFF CACHE BOOL "" FORCE)
endforeach()
if(ANDROID_ABI STREQUAL "arm64-v8a")
    set(GGML_CPU_ARM_ARCH "armv8-a" CACHE STRING "" FORCE)
endif()

FetchContent_Declare(llama_cpp
    URL "${AGENT_LLAMA_ARCHIVE}"
    URL_HASH SHA256=a6861d549427f814dc591c439e08206f67ffaba0248344d421589abf18199e67
)
FetchContent_MakeAvailable(llama_cpp)

add_library(agent_qwen SHARED local_model_jni.cpp)
target_compile_features(agent_qwen PRIVATE cxx_std_17)
target_include_directories(agent_qwen PRIVATE "${llama_cpp_SOURCE_DIR}/vendor")
target_compile_definitions(agent_qwen PRIVATE AGENT_LLAMA_REVISION="${AGENT_LLAMA_REVISION}")
target_compile_options(agent_qwen PRIVATE -Wall -Wextra -Werror=return-type)
target_link_libraries(agent_qwen PRIVATE llama mtmd log android)
target_link_options(agent_qwen PRIVATE "-Wl,-z,max-page-size=16384")
