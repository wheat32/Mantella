# Builds the four SKSE plugins (.dll) the Mantella mod needs, from source, against CommonLibSSE-NG.
#
# The plugins find their way around the game through the Address Library, so they do not have to be rebuilt for
# every game update. They do have to be rebuilt when the format of the Address Library changes (as it did with
# Skyrim 1.7.99), which is done by raising COMMONLIBSSE_NG_TAG to a release of CommonLibSSE-NG that supports it.
cmake_minimum_required(VERSION 3.24)

project(MantellaSKSEPlugins VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(BUILD_SHARED_LIBS OFF)

# The release of CommonLibSSE-NG to build against (a tag or commit of https://github.com/alandtse/CommonLibVR)
set(COMMONLIBSSE_NG_TAG "8ffc2b74af015f837de53cc02b0cb470a15678e4" CACHE STRING "CommonLibSSE-NG version (v12.1.0)")

# CommonLibSSE-NG options: no tests, and no Skyrim VR (not supported by these builds, and it would need OpenVR)
set(BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(ENABLE_SKYRIM_VR OFF CACHE BOOL "" FORCE)

include(FetchContent)
FetchContent_Declare(commonlibsse_ng
    GIT_REPOSITORY https://github.com/alandtse/CommonLibVR.git
    GIT_TAG ${COMMONLIBSSE_NG_TAG}
    GIT_SUBMODULES "")
FetchContent_MakeAvailable(commonlibsse_ng)
include(${commonlibsse_ng_SOURCE_DIR}/cmake/CommonLibSSE.cmake)

# HTTP client and JSON library used by SKSE_HTTP (from vcpkg, see vcpkg.json)
find_package(cpr CONFIG REQUIRED)
find_package(nlohmann_json CONFIG REQUIRED)

function(add_mantella_plugin TARGET FOLDER)
    list(TRANSFORM ARGN PREPEND "${FOLDER}/" OUTPUT_VARIABLE plugin_sources)
    add_commonlibsse_plugin(${TARGET} SOURCES ${plugin_sources})
    target_compile_features(${TARGET} PRIVATE cxx_std_23)
    # UNICODE: the plugins call the wide-character versions of the Windows API (as CommonLibSSE-NG's own builds do)
    target_compile_definitions(${TARGET} PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN UNICODE _UNICODE)
    target_include_directories(${TARGET} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/${FOLDER}")
    target_precompile_headers(${TARGET} PRIVATE "${FOLDER}/PCH.h")
    # All plugins end up in one folder: <build folder>/plugins
    set_target_properties(${TARGET} PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/plugins"
        RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}/plugins")
endfunction()

add_mantella_plugin(MantellaLauncher MantellaLauncher plugin.cpp)
add_mantella_plugin(MantellaDialogue MantellaDialogue plugin.cpp)
add_mantella_plugin(MantellaSubtitles MantellaSubtitles plugin.cpp Papyrus.cpp InjectTopic.cpp)
add_mantella_plugin(SKSE_HTTP SKSE_HTTP plugin.cpp src/TypedDictionary.cpp src/SKSE_HTTP_TypedDictionary.cpp src/FrameCapture.cpp src/DialogueOptions.cpp src/NotableItems.cpp src/NearbyObjects.cpp src/OwnedItems.cpp)
target_include_directories(SKSE_HTTP PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/SKSE_HTTP/include")
target_link_libraries(SKSE_HTTP PRIVATE cpr::cpr nlohmann_json::nlohmann_json)
