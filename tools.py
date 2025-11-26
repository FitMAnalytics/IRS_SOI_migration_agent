from pathlib import Path
import time
import io, os, traceback
import contextlib
import sys
from typing import Any, Dict, List
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def execute_python_code(env: dict = {}, code: str = "", verbose: bool = False) -> dict:
    """
    Execute arbitrary Python code in a given environment env.

    Args:
        code: Python source code as a string.
        env: dict representing the execution environment (namespace).
        verbose: If True, print the code and its stdout to the local console.

    Returns:
        dict with:
            - success: bool
            - stdout: captured standard output (str)
            - stderr: captured standard error (str)
            - figures: list of matplotlib.figure.Figure objects
            - execution_time_seconds: float
            - error / error_type (only on failure)
    """
    start_time = time.time()

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    pd = None
    np = None
    plt = None
    sns = None

    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    import seaborn as sns

    env.update({"pd": pd, "np": np, "plt": plt, "sns": sns})

    if verbose:
        print("\n[Executing Python Code]")
        print("-" * 60)
        print(code)
        print("-" * 60)

    try:
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            if plt is not None:
                plt.show()
                plt.close("all")
            
            # --- Monkey-patch plt.show so it doesn't clear figures ---
            original_show = plt.show

            def _noop_show(*args, **kwargs):
                return

            plt.show = _noop_show
            try:
                exec(code, env)
            finally:
                plt.show = original_show


            if plt is not None:
                figures = [plt.figure(num) for num in plt.get_fignums()]
                if verbose:
                    print(f"current plt figures: {plt.get_fignums()}")
            else: 
                figures = []
        
        stdout_output = stdout_buf.getvalue()
        stderr_output = stderr_buf.getvalue()
        elapsed = time.time() - start_time

        if verbose:
            if stdout_output:
                print(stdout_output, end="")
            if stderr_output:
                print(stderr_output, end="")

        return {
            "success": True,
            "stdout": stdout_output,
            "stderr": stderr_output,
            "execution_time_seconds": round(elapsed, 4),
            "figures": figures,
        }

    except Exception as e:
        elapsed = time.time() - start_time
        tb_str = traceback.format_exc()
        if verbose:
            print("[ERROR]")
            print(tb_str)

        return {
            "success": False,
            "stdout": stdout_buf.getvalue(),
            "stderr": stderr_buf.getvalue(),
            "execution_time_seconds": round(elapsed, 4),
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": tb_str,
        }