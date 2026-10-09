cmake_minimum_required(VERSION 3.22)
project(agent_qwen LANGUAGES C CXX)

include(ExternalProject)
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
set(AGENT_LLAMA_OPTIONS
    BUILD_SHARED_LIBS LLAMA_BUILD_IS_DEV LLAMA_BUILD_COMMON LLAMA_BUILD_TOOLS LLAMA_BUILD_TESTS
    LLAMA_BUILD_EXAMPLES LLAMA_BUILD_SERVER MTMD_VIDEO LLAMA_OPENSSL LLAMA_SUBPROCESS
    GGML_BACKEND_DL GGML_NATIVE GGML_OPENMP GGML_BLAS GGML_LLAMAFILE GGML_CPU_REPACK
    GGML_CPU_KLEIDIAI GGML_VULKAN GGML_CUDA GGML_METAL GGML_SYCL
    GGML_SSE42 GGML_AVX GGML_AVX2 GGML_BMI2 GGML_FMA GGML_F16C GGML_AVX512)
set(AGENT_LLAMA_ARGUMENTS -DLLAMA_BUILD_MTMD=ON -DCMAKE_POSITION_INDEPENDENT_CODE=ON)
foreach(option IN LISTS AGENT_LLAMA_OPTIONS)
    set(${option} OFF CACHE BOOL "" FORCE)
    list(APPEND AGENT_LLAMA_ARGUMENTS "-D${option}=OFF")
endforeach()
set(LLAMA_BUILD_MTMD ON CACHE BOOL "" FORCE)
if(ANDROID_ABI STREQUAL "arm64-v8a")
    set(GGML_CPU_ARM_ARCH "armv8-a" CACHE STRING "" FORCE)
endif()

FetchContent_Declare(llama_cpp
    URL "${AGENT_LLAMA_ARCHIVE}"
    URL_HASH SHA256=a6861d549427f814dc591c439e08206f67ffaba0248344d421589abf18199e67
)
FetchContent_MakeAvailable(llama_cpp)

function(agent_qwen_library name)
    add_library(${name} SHARED local_model_jni.cpp)
    target_compile_features(${name} PRIVATE cxx_std_17)
    target_include_directories(${name} PRIVATE "${llama_cpp_SOURCE_DIR}/vendor")
    target_compile_definitions(${name} PRIVATE AGENT_LLAMA_REVISION="${AGENT_LLAMA_REVISION}")
    target_compile_options(${name} PRIVATE -Wall -Wextra -Werror=return-type)
    target_link_options(${name} PRIVATE "-Wl,-z,max-page-size=16384")
endfunction()

agent_qwen_library(agent_qwen)
target_link_libraries(agent_qwen PRIVATE llama mtmd log android)

if(ANDROID_ABI STREQUAL "arm64-v8a")
    # The same pinned source compiled for ARMv8.2 dot products and FP16 arithmetic
    # (ggml's android_armv8.2_2 feature set). Without them the 2B model evaluated
    # about 20 prompt tokens a second on a Snapdragon 888. LocalModelBridge loads
    # this library only when every CPU core reports asimddp and asimdhp.
    set(dotprod_dir "${CMAKE_CURRENT_BINARY_DIR}/llama-dotprod")
    set(dotprod_libraries
        "${dotprod_dir}/tools/mtmd/libmtmd.a"
        "${dotprod_dir}/src/libllama.a"
        "${dotprod_dir}/ggml/src/libggml.a"
        "${dotprod_dir}/ggml/src/libggml-cpu.a"
        "${dotprod_dir}/ggml/src/libggml-base.a"
        "${dotprod_dir}/vendor/hash/libvendor-hash.a")
    ExternalProject_Add(llama_dotprod
        SOURCE_DIR "${llama_cpp_SOURCE_DIR}"
        BINARY_DIR "${dotprod_dir}"
        CMAKE_ARGS
            "-DCMAKE_TOOLCHAIN_FILE=${CMAKE_TOOLCHAIN_FILE}"
            "-DANDROID_ABI=${ANDROID_ABI}"
            "-DANDROID_PLATFORM=${ANDROID_PLATFORM}"
            "-DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}"
            "-DCMAKE_MAKE_PROGRAM=${CMAKE_MAKE_PROGRAM}"
            "-DCMAKE_PROJECT_INCLUDE=${CMAKE_CURRENT_SOURCE_DIR}/optimize.cmake"
            ${AGENT_LLAMA_ARGUMENTS}
            "-DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod+fp16"
        BUILD_COMMAND "${CMAKE_COMMAND}" --build "${dotprod_dir}" --target mtmd
        INSTALL_COMMAND ""
        BUILD_BYPRODUCTS ${dotprod_libraries})

    agent_qwen_library(agent_qwen_dotprod)
    add_dependencies(agent_qwen_dotprod llama_dotprod)
    target_include_directories(agent_qwen_dotprod PRIVATE
        "${llama_cpp_SOURCE_DIR}/include" "${llama_cpp_SOURCE_DIR}/ggml/include"
        "${llama_cpp_SOURCE_DIR}/tools/mtmd")
    target_link_libraries(agent_qwen_dotprod PRIVATE
        -Wl,--start-group ${dotprod_libraries} -Wl,--end-group log android m)
else()
    # Gradle builds the same target list for every ABI; the APK excludes this copy.
    agent_qwen_library(agent_qwen_dotprod)
    target_link_libraries(agent_qwen_dotprod PRIVATE llama mtmd log android)
endif()
