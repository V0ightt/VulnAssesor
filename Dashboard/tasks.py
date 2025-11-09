import time
from celery import shared_task


@shared_task
def simple_test_task(task_duration_seconds):
    """
    A simple test task that sleeps for a given duration.
    """
    print(f"Task started! Will run for {task_duration_seconds} seconds.")

    for i in range(task_duration_seconds):
        time.sleep(1)
        print(f"Task running... {i + 1} seconds passed.")

    print("Task finished!")
    return f"Task complete after {task_duration_seconds} seconds."