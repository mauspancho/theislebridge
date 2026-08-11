#include <elf.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <deque>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <thread>
#include <unordered_map>
#include <vector>

namespace {

using UObject = void;
using UFunction = void;
using ProcessEventFn = void (*)(UObject*, UFunction*, void*);

constexpr std::string_view kSupportedBuildId = "cf63a41bf6a6fcbf";
constexpr uintptr_t kGUObjectArray = 0xC95C600;
constexpr uintptr_t kNamePool = 0xC8A10F0;
constexpr uintptr_t kGEngine = 0xCAE7630;
constexpr size_t kGameEngineTickSlot = 0x310 / sizeof(void*);
constexpr size_t kProcessEventSlot = 0x268 / sizeof(void*);
constexpr size_t kObjectsPerChunk = 65536;
constexpr size_t kFUObjectItemSize = 0x18;
constexpr size_t kPrimeBytes = 0x0B;

constexpr ptrdiff_t UObject_ClassPrivate = 0x10;
constexpr ptrdiff_t UObject_NamePrivate = 0x18;
constexpr ptrdiff_t UStruct_SuperStruct = 0x40;
constexpr ptrdiff_t UStruct_ChildProperties = 0x50;
constexpr ptrdiff_t UStruct_PropertiesSize = 0x58;
constexpr ptrdiff_t UFunction_NumParms = 0xB4;
constexpr ptrdiff_t UFunction_ParmsSize = 0xB6;
constexpr ptrdiff_t UFunction_ReturnValueOffset = 0xB8;
constexpr ptrdiff_t FField_Next = 0x18;
constexpr ptrdiff_t FField_NamePrivate = 0x20;
constexpr ptrdiff_t FProperty_OffsetInternal = 0x44;

std::atomic_bool g_running{true};
std::atomic_bool g_in_call{false};
std::string g_build_id;
bool g_build_supported = false;

using GameEngineTickFn = void (*)(void*, float, bool);
GameEngineTickFn g_original_tick = nullptr;
std::atomic_bool g_tick_hooked{false};

struct PendingRequest {
    std::filesystem::path runtime;
    std::filesystem::path request_path;
    std::string request_id;
    std::string action;
    std::string player;
};

std::mutex g_pending_mutex;
std::deque<PendingRequest> g_pending;

template <typename T>
T read_value(uintptr_t address) {
    return *reinterpret_cast<T*>(address);
}

std::string hex_bytes(const uint8_t* data, size_t len) {
    char buf[4] = {};
    std::string out;
    for (size_t i = 0; i < len; ++i) {
        std::snprintf(buf, sizeof(buf), "%02x", data[i]);
        if (i) out.push_back(' ');
        out += buf;
    }
    return out;
}

void log_line(const std::string& message) {
    std::fprintf(stderr, "[TheIsleBridgeNative] %s\n", message.c_str());
    std::fflush(stderr);
}

bool looks_mapped(uintptr_t address) {
    if (address < 0x10000) {
        return false;
    }
    unsigned char vec = 0;
    int fd = ::open("/proc/self/mem", O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        return false;
    }
    const ssize_t got = ::pread(fd, &vec, 1, static_cast<off_t>(address));
    ::close(fd);
    return got == 1;
}

std::string decode_name(uint32_t comparison_index) {
    auto blocks = read_value<uintptr_t*>(kNamePool + 0x10);
    const uint32_t block = comparison_index >> 16;
    const uint32_t offset = comparison_index & 0xFFFF;
    uintptr_t block_ptr = reinterpret_cast<uintptr_t>(blocks[block]);
    if (!looks_mapped(block_ptr)) return {};
    uintptr_t entry = block_ptr + static_cast<uintptr_t>(offset) * 2;
    uint16_t header = read_value<uint16_t>(entry);
    const bool wide = (header & 1) != 0;
    const uint16_t len = header >> 6;
    if (len == 0 || len > 512) return {};
    std::string out;
    out.reserve(len);
    if (wide) {
        auto chars = reinterpret_cast<const char16_t*>(entry + 2);
        for (uint16_t i = 0; i < len; ++i) {
            char16_t c = chars[i];
            out.push_back(c < 0x80 ? static_cast<char>(c) : '?');
        }
    } else {
        auto chars = reinterpret_cast<const char*>(entry + 2);
        out.assign(chars, chars + len);
    }
    return out;
}

std::string object_name(UObject* object) {
    if (!object) return {};
    const uint32_t index = read_value<uint32_t>(reinterpret_cast<uintptr_t>(object) + UObject_NamePrivate);
    return decode_name(index);
}

UObject* object_class(UObject* object) {
    if (!object) return nullptr;
    return read_value<UObject*>(reinterpret_cast<uintptr_t>(object) + UObject_ClassPrivate);
}

std::string class_name(UObject* object) {
    return object_name(object_class(object));
}

bool class_derives_from(UObject* klass, std::string_view wanted) {
    for (UObject* current = klass; current; current = read_value<UObject*>(reinterpret_cast<uintptr_t>(current) + UStruct_SuperStruct)) {
        if (object_name(current) == wanted) return true;
    }
    return false;
}

struct FUObjectArrayView {
    uintptr_t chunks = 0;
    int32_t num_elements = 0;
    int32_t num_chunks = 0;
};

FUObjectArrayView object_array() {
    FUObjectArrayView view;
    view.chunks = read_value<uintptr_t>(kGUObjectArray + 0x10);
    view.num_elements = read_value<int32_t>(kGUObjectArray + 0x24);
    view.num_chunks = read_value<int32_t>(kGUObjectArray + 0x2C);
    return view;
}

UObject* object_at(const FUObjectArrayView& view, int32_t index) {
    if (index < 0 || index >= view.num_elements) return nullptr;
    const int32_t chunk_index = index / static_cast<int32_t>(kObjectsPerChunk);
    const int32_t within = index % static_cast<int32_t>(kObjectsPerChunk);
    if (chunk_index < 0 || chunk_index >= view.num_chunks) return nullptr;
    uintptr_t chunk = read_value<uintptr_t>(view.chunks + sizeof(uintptr_t) * chunk_index);
    if (!looks_mapped(chunk)) return nullptr;
    uintptr_t item = chunk + static_cast<uintptr_t>(within) * kFUObjectItemSize;
    UObject* object = read_value<UObject*>(item);
    return looks_mapped(reinterpret_cast<uintptr_t>(object)) ? object : nullptr;
}

std::vector<UObject*> all_objects_named(std::string_view name) {
    std::vector<UObject*> matches;
    const auto view = object_array();
    for (int32_t i = 0; i < view.num_elements; ++i) {
        UObject* object = object_at(view, i);
        if (object && object_name(object) == name) {
            matches.push_back(object);
        }
    }
    return matches;
}

std::optional<int32_t> property_offset(UObject* struct_object, std::string_view property_name) {
    for (UObject* current = struct_object; current; current = read_value<UObject*>(reinterpret_cast<uintptr_t>(current) + UStruct_SuperStruct)) {
        uintptr_t field = read_value<uintptr_t>(reinterpret_cast<uintptr_t>(current) + UStruct_ChildProperties);
        while (looks_mapped(field)) {
            const uint32_t name_index = read_value<uint32_t>(field + FField_NamePrivate);
            if (decode_name(name_index) == property_name) {
                return read_value<int32_t>(field + FProperty_OffsetInternal);
            }
            field = read_value<uintptr_t>(field + FField_Next);
        }
    }
    return std::nullopt;
}

std::string read_fstring(uintptr_t address) {
    uintptr_t data = read_value<uintptr_t>(address);
    int32_t count = read_value<int32_t>(address + 0x08);
    if (!looks_mapped(data) || count <= 0 || count > 1024) return {};
    std::u16string raw(reinterpret_cast<char16_t*>(data), reinterpret_cast<char16_t*>(data) + count - 1);
    std::string out;
    out.reserve(raw.size());
    for (char16_t c : raw) out.push_back(c < 0x80 ? static_cast<char>(c) : '?');
    return out;
}

struct PlayerDino {
    UObject* dino = nullptr;
    UObject* controller = nullptr;
    UObject* player_state = nullptr;
    std::string dinosaur_class;
};

std::vector<PlayerDino> resolve_player_dinos(const std::string& player_name) {
    std::vector<PlayerDino> matches;
    const auto view = object_array();
    for (int32_t i = 0; i < view.num_elements; ++i) {
        UObject* dino = object_at(view, i);
        if (!dino) continue;
        UObject* dino_class = object_class(dino);
        if (!class_derives_from(dino_class, "TIDinosaurBase")) continue;
        auto controller_offset = property_offset(dino_class, "Controller");
        if (!controller_offset) continue;
        UObject* controller = read_value<UObject*>(reinterpret_cast<uintptr_t>(dino) + *controller_offset);
        if (!controller || !class_derives_from(object_class(controller), "PlayerController")) continue;
        if (class_derives_from(object_class(controller), "AIController")) continue;
        auto player_state_offset = property_offset(object_class(controller), "PlayerState");
        if (!player_state_offset) continue;
        UObject* player_state = read_value<UObject*>(reinterpret_cast<uintptr_t>(controller) + *player_state_offset);
        if (!player_state) continue;
        auto player_name_offset = property_offset(object_class(player_state), "PlayerNamePrivate");
        if (!player_name_offset) continue;
        const std::string observed = read_fstring(reinterpret_cast<uintptr_t>(player_state) + *player_name_offset);
        if (observed == player_name) {
            matches.push_back(PlayerDino{dino, controller, player_state, class_name(dino)});
        }
    }
    return matches;
}

bool validate_prime_function(UObject* fn, uint16_t parms_size, uint16_t return_offset) {
    if (!fn) return false;
    const uint16_t observed_parms = read_value<uint16_t>(reinterpret_cast<uintptr_t>(fn) + UFunction_ParmsSize);
    const uint16_t observed_return = read_value<uint16_t>(reinterpret_cast<uintptr_t>(fn) + UFunction_ReturnValueOffset);
    return observed_parms == parms_size && observed_return == return_offset;
}

UObject* single_function(std::string_view name) {
    auto matches = all_objects_named(name);
    if (matches.size() != 1) {
        log_line("function discovery failed for " + std::string(name) + " matches=" + std::to_string(matches.size()));
        return nullptr;
    }
    return matches.front();
}

bool call_process_event(UObject* dino, UObject* function, void* params) {
    if (g_in_call.exchange(true)) {
        return false;
    }
    struct Guard {
        ~Guard() { g_in_call = false; }
    } guard;
    void** vtable = *reinterpret_cast<void***>(dino);
    auto process_event = reinterpret_cast<ProcessEventFn>(vtable[kProcessEventSlot]);
    if (!looks_mapped(reinterpret_cast<uintptr_t>(process_event))) return false;
    process_event(dino, reinterpret_cast<UFunction*>(function), params);
    return true;
}

struct PrimeStatus {
    bool success = false;
    std::string error;
    std::string dinosaur;
    bool eligible = false;
    bool prime = false;
    bool already_prime = false;
};

PrimeStatus execute_prime(const std::string& action, const std::string& player_name) {
    if (!g_build_supported) {
        return {.success = false, .error = "UNSUPPORTED_BUILD"};
    }
    const auto players = resolve_player_dinos(player_name);
    if (players.empty()) return {.success = false, .error = "PLAYER_NOT_FOUND"};
    if (players.size() > 1) return {.success = false, .error = "AMBIGUOUS_PLAYER"};
    const auto target = players.front();

    UObject* get_eligible = single_function("GetEligiblePrimeElderData");
    UObject* set_eligible = single_function("SetEligiblePrimeElderData");
    UObject* get_is_eligible = single_function("GetIsEligiblePrimeElder");
    UObject* is_prime = single_function("IsPrimeElder");
    if (!validate_prime_function(get_eligible, 0x0B, 0x0000)) return {.success = false, .error = "BAD_GET_ELIGIBLE_SIGNATURE"};
    if (!validate_prime_function(set_eligible, 0x0B, 0xFFFF)) return {.success = false, .error = "BAD_SET_ELIGIBLE_SIGNATURE"};
    if (!validate_prime_function(get_is_eligible, 0x01, 0x0000)) return {.success = false, .error = "BAD_GET_IS_ELIGIBLE_SIGNATURE"};
    if (!validate_prime_function(is_prime, 0x01, 0x0000)) return {.success = false, .error = "BAD_IS_PRIME_SIGNATURE"};

    std::array<uint8_t, kPrimeBytes> current{};
    uint8_t eligible = 0;
    uint8_t prime = 0;
    if (!call_process_event(target.dino, get_eligible, current.data())) return {.success = false, .error = "GET_ELIGIBLE_FAILED"};
    if (!call_process_event(target.dino, get_is_eligible, &eligible)) return {.success = false, .error = "GET_IS_ELIGIBLE_FAILED"};
    if (!call_process_event(target.dino, is_prime, &prime)) return {.success = false, .error = "IS_PRIME_FAILED"};

    if (action == "STATUS") {
        return {.success = true, .dinosaur = target.dinosaur_class, .eligible = eligible != 0, .prime = prime != 0};
    }
    if (eligible && prime) {
        return {.success = true, .error = "", .dinosaur = target.dinosaur_class, .eligible = true, .prime = true, .already_prime = true};
    }

    std::array<uint8_t, kPrimeBytes> desired{};
    desired.fill(1);
    std::array<uint8_t, kPrimeBytes> verify{};
    if (!call_process_event(target.dino, set_eligible, desired.data())) return {.success = false, .error = "SET_ELIGIBLE_FAILED"};
    if (!call_process_event(target.dino, get_eligible, verify.data())) return {.success = false, .error = "VERIFY_GET_FAILED"};
    const bool bytes_ok = std::all_of(verify.begin(), verify.end(), [](uint8_t value) { return value == 1; });
    eligible = 0;
    prime = 0;
    call_process_event(target.dino, get_is_eligible, &eligible);
    call_process_event(target.dino, is_prime, &prime);
    if (!bytes_ok || !eligible || !prime) {
        log_line("prime verify failed bytes=" + hex_bytes(verify.data(), verify.size()));
        return {.success = false, .error = "VERIFY_FAILED", .dinosaur = target.dinosaur_class, .eligible = eligible != 0, .prime = prime != 0};
    }
    return {.success = true, .dinosaur = target.dinosaur_class, .eligible = true, .prime = true};
}

std::unordered_map<std::string, std::string> read_request(const std::filesystem::path& path) {
    std::unordered_map<std::string, std::string> out;
    std::ifstream file(path);
    std::string line;
    while (std::getline(file, line)) {
        auto eq = line.find('=');
        if (eq == std::string::npos) continue;
        out[line.substr(0, eq)] = line.substr(eq + 1);
    }
    return out;
}

void write_result(const std::filesystem::path& runtime, const std::string& request_id, const PrimeStatus& status, const std::string& player) {
    const auto dir = runtime / "results";
    std::filesystem::create_directories(dir);
    const auto tmp = dir / ("result-" + request_id + ".tmp");
    const auto final = dir / ("result-" + request_id + ".result");
    std::ofstream file(tmp);
    file << "REQUEST_ID=" << request_id << "\n";
    file << "SUCCESS=" << (status.success ? "1" : "0") << "\n";
    file << "ERROR=" << status.error << "\n";
    file << "PLAYER=" << player << "\n";
    file << "DINOSAUR=" << status.dinosaur << "\n";
    file << "ELIGIBLE_PRIME=" << (status.eligible ? "1" : "0") << "\n";
    file << "PRIME=" << (status.prime ? "1" : "0") << "\n";
    file << "ALREADY_PRIME=" << (status.already_prime ? "1" : "0") << "\n";
    file << "BUILD_SUPPORTED=" << (g_build_supported ? "1" : "0") << "\n";
    file << "BUILD_ID=" << g_build_id << "\n";
    file.close();
    std::filesystem::rename(tmp, final);
}

void hooked_game_engine_tick(void* self, float delta_seconds, bool idle_mode) {
    if (g_original_tick) {
        g_original_tick(self, delta_seconds, idle_mode);
    }
    std::deque<PendingRequest> local;
    {
        std::lock_guard<std::mutex> lock(g_pending_mutex);
        local.swap(g_pending);
    }
    for (const auto& request : local) {
        PrimeStatus status = execute_prime(request.action, request.player);
        write_result(request.runtime, request.request_id, status, request.player);
        try {
            std::filesystem::rename(
                request.request_path,
                request.runtime / "requests" / ("request-" + request.request_id + ".done"));
        } catch (const std::exception& exc) {
            log_line(std::string("request archive failed=") + exc.what());
        }
    }
}

bool make_writable(void* address) {
    const long page_size = ::sysconf(_SC_PAGESIZE);
    if (page_size <= 0) return false;
    const uintptr_t page = reinterpret_cast<uintptr_t>(address) & ~(static_cast<uintptr_t>(page_size) - 1);
    return ::mprotect(reinterpret_cast<void*>(page), static_cast<size_t>(page_size), PROT_READ | PROT_WRITE | PROT_EXEC) == 0;
}

bool install_tick_hook() {
    if (g_tick_hooked || !g_build_supported) return g_tick_hooked;
    if (!looks_mapped(kGEngine)) return false;
    UObject* engine = read_value<UObject*>(kGEngine);
    if (!engine || !looks_mapped(reinterpret_cast<uintptr_t>(engine))) return false;
    void** vtable = *reinterpret_cast<void***>(engine);
    if (!looks_mapped(reinterpret_cast<uintptr_t>(vtable))) return false;
    void** slot = &vtable[kGameEngineTickSlot];
    if (!looks_mapped(reinterpret_cast<uintptr_t>(*slot))) return false;
    if (!make_writable(slot)) {
        log_line("failed to make GameEngine vtable writable");
        return false;
    }
    g_original_tick = reinterpret_cast<GameEngineTickFn>(*slot);
    *slot = reinterpret_cast<void*>(&hooked_game_engine_tick);
    g_tick_hooked = true;
    log_line("GameEngine::Tick hook installed through vtable slot +0x310");
    return true;
}

std::string read_build_id() {
    std::ifstream file("/proc/self/exe", std::ios::binary);
    if (!file) return {};
    Elf64_Ehdr ehdr{};
    file.read(reinterpret_cast<char*>(&ehdr), sizeof(ehdr));
    if (!file || std::memcmp(ehdr.e_ident, ELFMAG, SELFMAG) != 0) return {};
    file.seekg(ehdr.e_phoff);
    std::vector<Elf64_Phdr> phdrs(ehdr.e_phnum);
    file.read(reinterpret_cast<char*>(phdrs.data()), static_cast<std::streamsize>(phdrs.size() * sizeof(Elf64_Phdr)));
    for (const auto& phdr : phdrs) {
        if (phdr.p_type != PT_NOTE) continue;
        std::vector<char> notes(phdr.p_filesz);
        file.seekg(phdr.p_offset);
        file.read(notes.data(), static_cast<std::streamsize>(notes.size()));
        size_t pos = 0;
        while (pos + sizeof(Elf64_Nhdr) <= notes.size()) {
            auto* note = reinterpret_cast<const Elf64_Nhdr*>(notes.data() + pos);
            pos += sizeof(Elf64_Nhdr);
            const char* name = notes.data() + pos;
            pos += ((note->n_namesz + 3) / 4) * 4;
            const unsigned char* desc = reinterpret_cast<const unsigned char*>(notes.data() + pos);
            pos += ((note->n_descsz + 3) / 4) * 4;
            if (note->n_type == NT_GNU_BUILD_ID && note->n_namesz >= 3 && std::strncmp(name, "GNU", 3) == 0) {
                std::string out;
                char buf[3] = {};
                for (uint32_t i = 0; i < note->n_descsz; ++i) {
                    std::snprintf(buf, sizeof(buf), "%02x", desc[i]);
                    out += buf;
                }
                return out;
            }
        }
    }
    return {};
}

void worker() {
    const char* runtime_env = std::getenv("THEISLE_BRIDGE_RUNTIME_DIR");
    const std::filesystem::path runtime = runtime_env ? runtime_env : "/run/theisle-server-bridge";
    std::filesystem::create_directories(runtime / "requests");
    std::filesystem::create_directories(runtime / "results");

    g_build_id = read_build_id();
    g_build_supported = g_build_id == kSupportedBuildId;
    log_line("startup build_id=" + g_build_id + " supported=" + (g_build_supported ? std::string("true") : std::string("false")));

    while (g_running) {
        try {
            const auto request_dir = runtime / "requests";
            for (const auto& entry : std::filesystem::directory_iterator(request_dir)) {
                if (entry.path().extension() != ".req") continue;
                auto request = read_request(entry.path());
                const auto request_id = request["REQUEST_ID"];
                const auto action = request["ACTION"];
                const auto player = request["PLAYER_NAME"];
                if (request_id.empty() || player.empty() || (action != "PRIME" && action != "STATUS")) {
                    std::filesystem::remove(entry.path());
                    continue;
                }
                log_line("request action=" + action + " player=" + player);
                if (!g_build_supported) {
                    write_result(runtime, request_id, PrimeStatus{.success = false, .error = "UNSUPPORTED_BUILD"}, player);
                    std::filesystem::rename(entry.path(), runtime / "requests" / ("request-" + request_id + ".done"));
                    continue;
                }
                if (!install_tick_hook()) {
                    continue;
                }
                const auto processing = runtime / "requests" / ("request-" + request_id + ".processing");
                std::filesystem::rename(entry.path(), processing);
                {
                    std::lock_guard<std::mutex> lock(g_pending_mutex);
                    g_pending.push_back(PendingRequest{runtime, processing, request_id, action, player});
                }
            }
        } catch (const std::exception& exc) {
            log_line(std::string("worker error=") + exc.what());
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

__attribute__((constructor)) void on_load() {
    static std::thread thread([] { worker(); });
    thread.detach();
}

__attribute__((destructor)) void on_unload() {
    g_running = false;
}

}  // namespace
