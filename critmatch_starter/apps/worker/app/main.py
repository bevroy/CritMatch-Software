import os
import time


def main() -> None:
    interval = int(os.getenv("JOB_POLL_INTERVAL_SECONDS", "10"))
    print("CritMatch worker started. Polling for jobs...")
    while True:
        print("No jobs found. Sleeping...")
        time.sleep(interval)


if __name__ == "__main__":
    main()
