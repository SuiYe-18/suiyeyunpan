#include <windows.h>
#include <fstream>
#include <string>
using namespace std;

#define MAX_5GB 5368709120LL

extern "C" __declspec(dllexport) bool fastCopy(const char* src, const char* dst) {
    ifstream in(src, ios::binary);
    ofstream out(dst, ios::binary);
    if (!in || !out) return false;
    char buffer[1048576];
    while (in.read(buffer, sizeof(buffer))) {
        out.write(buffer, sizeof(buffer));
    }
    out.write(buffer, in.gcount());
    return true;
}

extern "C" __declspec(dllexport) bool isOver5GB(const char* path) {
    ifstream f(path, ios::ate | ios::binary);
    long long size = f.tellg();
    return size > MAX_5GB;
}

extern "C" __declspec(dllexport) long long getFileSize(const char* path) {
    ifstream f(path, ios::ate | ios::binary);
    return f.tellg();
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    return TRUE;
}