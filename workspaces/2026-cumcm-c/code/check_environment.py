from io import BytesIO

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import openpyxl
import pandas as pd
import scipy
from scipy.optimize import linprog


def main() -> None:
    result = linprog(
        c=np.array([1.0, 2.0]),
        A_ub=np.array([[-1.0, -1.0]]),
        b_ub=np.array([-1.0]),
        bounds=[(0.0, None), (0.0, None)],
        method="highs",
    )
    if not result.success or not np.isclose(result.fun, 1.0):
        raise RuntimeError(f"SciPy HiGHS smoke test failed: {result.message}")

    frame = pd.DataFrame({"value": [1.0, 2.0]})
    workbook = openpyxl.Workbook()
    workbook.active.append(frame.columns.tolist())
    workbook.active.append(frame.iloc[0].tolist())
    excel_buffer = BytesIO()
    workbook.save(excel_buffer)
    if excel_buffer.tell() == 0:
        raise RuntimeError("OpenPyXL smoke test produced an empty workbook")

    figure, axis = plt.subplots()
    axis.plot(frame.index, frame["value"])
    pdf_buffer = BytesIO()
    figure.savefig(pdf_buffer, format="pdf")
    plt.close(figure)
    if pdf_buffer.tell() == 0:
        raise RuntimeError("Matplotlib smoke test produced an empty PDF")

    print(f"Python scientific environment: PASS")
    print(f"NumPy {np.__version__}")
    print(f"SciPy {scipy.__version__} (HiGHS: PASS)")
    print(f"Pandas {pd.__version__}")
    print(f"OpenPyXL {openpyxl.__version__} (in-memory XLSX: PASS)")
    print(f"Matplotlib {matplotlib.__version__} (in-memory PDF: PASS)")


if __name__ == "__main__":
    main()
