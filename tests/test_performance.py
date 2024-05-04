from src.json_repair import repair_json

import os.path
import pathlib
path = pathlib.Path(__file__).parent.resolve()

fd = open(os.path.join(path,"valid.json"))
correct_json = fd.read()
fd.close()

fd = open(os.path.join(path,"invalid.json"))
incorrect_json = fd.read()
fd.close()

def test_true_true_correct(benchmark):
  benchmark(repair_json, correct_json, return_objects=True, skip_json_loads=True)
  
  # Retrieve the median execution time
  mean_time = benchmark.stats.get("median")

  # Define your time threshold in seconds
  max_time = 13 / 10 ** 4  # 1.3 millisecond

  # Assert that the average time is below the threshold
  assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"

def test_true_true_incorrect(benchmark):
  benchmark(repair_json, incorrect_json, return_objects=True, skip_json_loads=True)
  
  # Retrieve the median execution time
  mean_time = benchmark.stats.get("median")

  # Define your time threshold in seconds
  max_time = 13 / 10 ** 4  # 1.3 millisecond

  # Assert that the average time is below the threshold
  assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"

def test_true_false_correct(benchmark):
  benchmark(repair_json, correct_json, return_objects=True, skip_json_loads=False)
  # Retrieve the median execution time
  mean_time = benchmark.stats.get("median")

  # Define your time threshold in seconds
  max_time = 20 * (1 / 10 ** 6)  # 20 microsecond

  # Assert that the average time is below the threshold
  assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"

def test_true_false_incorrect(benchmark):
  benchmark(repair_json, incorrect_json, return_objects=True, skip_json_loads=False)
  # Retrieve the median execution time
  mean_time = benchmark.stats.get("median")

  # Define your time threshold in seconds
  max_time = 13 / 10 ** 4  # 1.3 millisecond

  # Assert that the average time is below the threshold
  assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"

def test_false_true_correct(benchmark):
  benchmark(repair_json, correct_json, return_objects=False, skip_json_loads=True)
  # Retrieve the median execution time
  mean_time = benchmark.stats.get("median")

  # Define your time threshold in seconds
  max_time = 13 / 10 ** 4  # 1.3 millisecond

  # Assert that the average time is below the threshold
  assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"

def test_false_true_incorrect(benchmark):
  benchmark(repair_json, incorrect_json, return_objects=False, skip_json_loads=True)
  # Retrieve the median execution time
  mean_time = benchmark.stats.get("median")
  
  # Define your time threshold in seconds
  max_time = 13 / 10 ** 4  # 1.3 millisecond

  # Assert that the average time is below the threshold
  assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"

def test_false_false_correct(benchmark):
  benchmark(repair_json, correct_json, return_objects=False, skip_json_loads=False)
  # Retrieve the median execution time
  mean_time = benchmark.stats.get("median")

  # Define your time threshold in seconds
  max_time = 50 / 10 ** 6  # 50 microsecond

  # Assert that the average time is below the threshold
  assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"

def test_false_false_incorrect(benchmark):
  benchmark(repair_json, incorrect_json, return_objects=False, skip_json_loads=False)
  # Retrieve the median execution time
  mean_time = benchmark.stats.get("median")

  # Define your time threshold in seconds
  max_time = 14 / 10 ** 4  # 1.4 millisecond

  # Assert that the average time is below the threshold
  assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"
