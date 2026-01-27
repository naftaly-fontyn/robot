import gc
import esp32
import micropython

def analyze_memory():
    """
    Runs a full memory analysis for MicroPython on the ESP32.
    
    This function calculates the total usable memory and then
    shows the low-level heap breakdown from the underlying ESP-IDF.
    """
    
    # Step 1: Run garbage collection to get the most accurate, clean state.
    gc.collect()
    
    print("============================================")
    print("      MicroPython Memory Analysis")
    print("============================================")

    # --- Part 1: The Total Usable Memory ---
    # This is the most important number for your script.
    # It = (Free in current MPY heap) + (Free in reserve heap)
    total_usable_mem = gc.mem_free()
    
    print(f"\n[ 1 ] Total Usable Memory for Script:")
    print(f"      {total_usable_mem} bytes  (~{total_usable_mem / 1024:.1f} KB)")
    print("--------------------------------------------")


    # --- Part 2: The MicroPython 'mem_info' View ---
    # This shows the two numbers that add up to the total above.
    print("\n[ 2 ] MicroPython Heap Breakdown (mem_info):")
    micropython.mem_info()
    print("--------------------------------------------")
    

    # --- Part 3: The ESP-IDF "Ground Truth" ---
    # This shows ALL data heaps, including the one MPY
    # uses for its "max new split" reserve.
    print("\n[ 3 ] ESP-IDF Data Heaps (Source of Truth):")
    print("      Legend: (Total, Free, Largest Free, Min Free)")
    
    # Get all DATA-capable heap regions
    idf_heaps = esp32.idf_heap_info(esp32.HEAP_DATA)
    
    mpy_reserve_heap = None
    
    for i, heap in enumerate(idf_heaps):
        print(f"      Heap {i}: {heap}")
        
        # Find the heap MPY uses as its reserve.
        # We assume it's the largest available one.
        if mpy_reserve_heap is None or heap[2] > mpy_reserve_heap[2]:
            mpy_reserve_heap = heap

    print("--------------------------------------------")


    # --- Part 4: Final Summary ---
    print("\n[ 4 ] Summary:")
    
    # The 'max new split' from Part 2 *should* match the
    # 'Largest Free' block from one of the heaps in Part 3.
    if mpy_reserve_heap:
        largest_block = mpy_reserve_heap[2] # 2 is the 'Largest Free' index
        print(f" > The largest block usable by MPY is {largest_block} bytes.")
        print(f"   (This should match the 'max new split' value from Part 2)")
    
    print(f" > The total you can use is {total_usable_mem} bytes (from Part 1).")
    print(" > The other small heaps in Part 3 are for internal")
    print("   use (e.g., Wi-Fi, Bluetooth) and not for your script.")
    print("============================================")

# --- To run the analysis ---
analyze_memory()