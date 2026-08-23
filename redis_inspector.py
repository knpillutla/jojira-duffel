#!/usr/bin/env python3
"""
Standalone Redis Cache Utility Inspector
Provides an interactive menu to view Redis cache keys/values,
inspect specific keys in full JSON format, track per-search cache hit metrics,
and view overall storage performance.

Usage:
    python redis_inspector.py
"""

import json
import os
import sys
import time
from typing import Any

# Ensure src is on Python module path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from duffel import DuffelClient


class RedisInspector:
    """Utility class for inspecting Redis cache contents and search hit metrics."""

    def __init__(self):
        self.client = DuffelClient()
        self.cache = self.client.cache

    def run(self):
        """Start the interactive inspector CLI loop."""
        while True:
            self._print_header()
            self._print_menu()
            choice = input("\n>> Select menu option (0-5): ").strip()

            if choice == "1":
                self._list_top_10_keys()
            elif choice == "2":
                self._inspect_specific_key()
            elif choice == "3":
                self._view_search_history_metrics()
            elif choice == "4":
                self._view_overall_cache_metrics()
            elif choice == "5":
                self._clear_cache()
            elif choice == "0":
                print("\nExiting Redis Inspector. Goodbye!")
                break
            else:
                print("\n[!] Invalid choice. Please select 0 to 5.")

            input("\nPress Enter to return to main menu...")

    def _print_header(self):
        print("\n" + "=" * 70)
        print("     DUFFEL API - REDIS CACHE INSPECTOR & METRICS UTILITY      ")
        print("=" * 70)
        status = self.cache.status_info
        backend_str = f"Redis ({status.get('redis_host')})" if status.get("backend") == "redis" else "In-Memory Fallback"
        print(f"  * Cache Status : {backend_str}")
        print(f"  * TTL Config   : {status.get('ttl_seconds')} seconds (1 Hour)")
        print("-" * 70)

    def _print_menu(self):
        print("  [1] List Top 10 Redis Cache Keys & Value Snippets")
        print("  [2] Inspect Complete JSON Value for a Specific Key")
        print("  [3] View Per-Search Cache Hits & Metrics History")
        print("  [4] View Overall Redis Storage & Performance Metrics")
        print("  [5] Clear / Flush Redis Cache Database")
        print("  [0] Exit")
        print("-" * 70)

    def _get_all_search_keys(self) -> list[str]:
        """Fetch all search cache keys from Redis."""
        if not self.cache.redis_client:
            return list(self.cache.in_memory_store.keys())
        try:
            return [k for k in self.cache.redis_client.keys("duffel:flights:search:*")]
        except Exception as err:
            print(f"\n[!] Error querying Redis keys: {err}")
            return []

    def _list_top_10_keys(self) -> list[str]:
        """Display top 10 keys with TTL and value snippet."""
        keys = self._get_all_search_keys()
        print(f"\n--- [1] TOP 10 REDIS CACHE KEYS (Total Cached Keys: {len(keys)}) ---")

        if not keys:
            print("\n  [i] No cache keys currently stored in Redis.")
            return []

        top_10 = keys[:10]
        for idx, key in enumerate(top_10, 1):
            ttl_sec = -1
            val_snippet = ""
            offers_cnt = 0

            if self.cache.redis_client:
                try:
                    ttl_sec = self.cache.redis_client.ttl(key)
                    raw_val = self.cache.redis_client.get(key)
                    if raw_val:
                        val_obj = json.loads(raw_val)
                        if isinstance(val_obj, dict):
                            offers_cnt = len(val_obj.get("offers", []))
                        val_snippet = str(raw_val)[:220]
                except Exception as err:
                    val_snippet = f"Error reading key: {err}"
            elif key in self.cache.in_memory_store:
                exp_t, raw_val = self.cache.in_memory_store[key]
                ttl_sec = max(0, int(exp_t - time.time()))
                val_snippet = raw_val[:220]

            print(f"\n  [{idx}] Key Name: {key}")
            print(f"      TTL Remaining : {ttl_sec} seconds | Cached Offers: {offers_cnt}")
            print(f"      Value Snippet : {val_snippet}...")
            print("-" * 70)

        return top_10

    def _inspect_specific_key(self):
        """Prompt user to pick or enter a key and print its full JSON content."""
        print("\n--- [2] INSPECT FULL JSON VALUE FOR A SPECIFIC KEY ---")
        keys = self._get_all_search_keys()

        if not keys:
            print("\n  [i] No cache keys available in Redis.")
            return

        print("\nAvailable Top 10 Keys:")
        top_10 = keys[:10]
        for idx, k in enumerate(top_10, 1):
            print(f"  [{idx}] {k}")

        user_input = input("\nEnter key number (1-10) or paste key name: ").strip()
        selected_key = None

        if user_input.isdigit():
            num = int(user_input)
            if 1 <= num <= len(top_10):
                selected_key = top_10[num - 1]

        if not selected_key:
            selected_key = user_input

        print(f"\n[+] Fetching content for Key: '{selected_key}'...")

        raw_val = None
        if self.cache.redis_client:
            try:
                raw_val = self.cache.redis_client.get(selected_key)
            except Exception as err:
                print(f"\n[!] Error reading from Redis: {err}")
        elif selected_key in self.cache.in_memory_store:
            _, raw_val = self.cache.in_memory_store[selected_key]

        if raw_val is None:
            print(f"\n[!] Key '{selected_key}' not found in cache.")
            return

        try:
            val_obj = json.loads(raw_val)
            pretty_json = json.dumps(val_obj, indent=2)
            print("\n" + "=" * 70)
            print(f"FULL JSON VALUE FOR KEY: {selected_key}")
            print("=" * 70)
            print(pretty_json)
            print("=" * 70)
        except Exception:
            print(f"\nRaw String Value:\n{raw_val}")

    def _view_search_history_metrics(self):
        """Display per-search metrics history showing cache hits vs API calls for each search."""
        print("\n--- [3] PER-SEARCH CACHE HITS & METRICS HISTORY ---")
        history = self.cache.get_search_history(limit=50)

        if not history:
            print("\n  [i] No search metrics history recorded yet.")
            print("      (Run flight searches via main.py to populate search metrics!)")
            return

        print(f"\n[+] Recorded Search History Events ({len(history)} Recent Searches):")
        print("=" * 110)
        print(
            f"{'#':<3} | {'Timestamp':<19} | {'Route':<11} | {'Outbound->Return':<23} | {'Duration':<11} | {'Batches':<7} | {'API Calls':<9} | {'Cache Hits':<10} | {'Hit %':<7} | {'Cheapest Price':<12}"
        )
        print("=" * 110)

        for idx, event in enumerate(history, 1):
            ts = event.get("timestamp", "N/A")
            route = event.get("route", "N/A")
            dates = f"{event.get('target_date', '')} -> {event.get('target_return_date', '')}"
            dur = event.get("duration_range", "N/A")
            batches = event.get("total_batches", 0)
            api_calls = event.get("api_calls", 0)
            hits = event.get("cache_hits", 0)
            hit_pct = f"{event.get('hit_percentage', 0.0):.1f}%"
            price = event.get("cheapest_price", "N/A")

            print(
                f"{idx:<3} | {ts:<19} | {route:<11} | {dates:<23} | {dur:<11} | {batches:<7} | {api_calls:<9} | {hits:<10} | {hit_pct:<7} | {price:<12}"
            )
        print("=" * 110)

    def _view_overall_cache_metrics(self):
        """Display overall Redis storage, read/write counts, and latency statistics."""
        print("\n--- [4] OVERALL REDIS CACHE STORAGE & PERFORMANCE METRICS ---")
        summary = self.cache.get_metrics_summary()

        print("\n=================================================================")
        print("REDIS CACHE PERFORMANCE SUMMARY")
        print("=================================================================")
        print(f"  * Cache Enabled       : {summary['enabled']}")
        print(f"  * Cache Backend       : {summary['backend'].upper()}")
        print(f"  * Redis Host          : {summary['redis_host']}")
        print(f"  * Total Cache Reads   : {summary['total_reads']}")
        print(f"  * Total Cache Hits    : {summary['hits']} ({summary['hit_percentage']}%)")
        print(f"  * Total Cache Misses  : {summary['misses']} ({summary['miss_percentage']}%)")
        print(f"  * Total Cache Writes  : {summary['writes']}")
        print(f"  * Read Latency        : Min {summary['read_min_ms']}ms | Max {summary['read_max_ms']}ms | Avg {summary['read_avg_ms']}ms")
        print(f"  * Write Latency       : Min {summary['write_min_ms']}ms | Max {summary['write_max_ms']}ms | Avg {summary['write_avg_ms']}ms")
        print(f"  * Configured TTL      : {summary['ttl_seconds']} seconds (1 Hour)")
        print("=================================================================")

    def _clear_cache(self):
        """Flush all cache entries upon user confirmation."""
        print("\n--- [5] CLEAR / FLUSH REDIS CACHE DATABASE ---")
        confirm = input("Are you sure you want to flush ALL cached Duffel entries in Redis? (y/n): ").strip().lower()
        if confirm in ("y", "yes"):
            self.cache.clear()
            print("\n[+] Redis cache database successfully cleared!")
        else:
            print("\nOperation cancelled. Cache intact.")


if __name__ == "__main__":
    inspector = RedisInspector()
    inspector.run()
