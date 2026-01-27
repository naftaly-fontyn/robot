import esp32

# Get info about all DATA heap regions
# (This includes internal RAM and external PSRAM)
heap_info = esp32.idf_heap_info(esp32.HEAP_DATA)

print("ESP-IDF Heap Info:")
print("(total, free, largest_free, min_free)")
print("----------------------------------------")

total_psram = 0

for heap in heap_info:
    print(heap)
    # PSRAM heaps are typically very large (e.g., > 1,000,000 bytes)
    # We'll assume any heap over 1MB is PSRAM
    if heap[0] > 1024 * 1024:
        total_psram += heap[0]

print("----------------------------------------")

if total_psram > 0:
    # Convert bytes to megabytes
    psram_mb = total_psram / 1024 / 1024
    print(f"Total PSRAM detected: {total_psram} bytes (~{psram_mb:.1f} MB)")
else:
    print("No large PSRAM heap detected.")