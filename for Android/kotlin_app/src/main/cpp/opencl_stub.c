/*
 * Link-time stand-in for the phone's own libOpenCL.so (see CMakeLists.txt).
 *
 * agent_qwen_opencl records a dependency on "libOpenCL.so" and Android resolves it to the
 * GPU vendor's library (for example /vendor/lib64/libOpenCL.so on Snapdragon phones). This
 * file is never packaged. Only the names matter, so the bodies are empty.
 *
 * The list is the OpenCL 2.0 API that ggml's OpenCL backend calls when built with
 * GGML_OPENCL_TARGET_VERSION=200. A newer llama.cpp pin that calls more of the API fails
 * to link here instead of failing to load on a phone whose driver lacks the function.
 */
#define AGENT_CL_STUB(name) void name(void) {}

AGENT_CL_STUB(clBuildProgram)
AGENT_CL_STUB(clCreateBuffer)
AGENT_CL_STUB(clCreateCommandQueue)
AGENT_CL_STUB(clCreateContext)
AGENT_CL_STUB(clCreateImage)
AGENT_CL_STUB(clCreateKernel)
AGENT_CL_STUB(clCreateProgramWithBinary)
AGENT_CL_STUB(clCreateProgramWithSource)
AGENT_CL_STUB(clCreateSubBuffer)
AGENT_CL_STUB(clEnqueueBarrierWithWaitList)
AGENT_CL_STUB(clEnqueueCopyBuffer)
AGENT_CL_STUB(clEnqueueFillBuffer)
AGENT_CL_STUB(clEnqueueMapBuffer)
AGENT_CL_STUB(clEnqueueMarkerWithWaitList)
AGENT_CL_STUB(clEnqueueNDRangeKernel)
AGENT_CL_STUB(clEnqueueReadBuffer)
AGENT_CL_STUB(clEnqueueUnmapMemObject)
AGENT_CL_STUB(clEnqueueWriteBuffer)
AGENT_CL_STUB(clFinish)
AGENT_CL_STUB(clFlush)
AGENT_CL_STUB(clGetDeviceIDs)
AGENT_CL_STUB(clGetDeviceInfo)
AGENT_CL_STUB(clGetEventProfilingInfo)
AGENT_CL_STUB(clGetKernelInfo)
AGENT_CL_STUB(clGetKernelWorkGroupInfo)
AGENT_CL_STUB(clGetPlatformIDs)
AGENT_CL_STUB(clGetPlatformInfo)
AGENT_CL_STUB(clGetProgramBuildInfo)
AGENT_CL_STUB(clGetProgramInfo)
AGENT_CL_STUB(clReleaseEvent)
AGENT_CL_STUB(clReleaseKernel)
AGENT_CL_STUB(clReleaseMemObject)
AGENT_CL_STUB(clReleaseProgram)
AGENT_CL_STUB(clSetKernelArg)
AGENT_CL_STUB(clWaitForEvents)
