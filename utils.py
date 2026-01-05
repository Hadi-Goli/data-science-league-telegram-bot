import io
import pandas as pd
import numpy as np
from sklearn.metrics import root_mean_squared_error
from typing import Tuple, Optional

# Hardcoded Whitelist of Full Names
WHITELIST = [
    "Hadi Goli",
    "Ali Alavi",
    "Sara Tehrani",
    "Test Student",
    "Admin User"
]

def check_whitelist(full_name: str) -> bool:
    """Check if the provided name is in the whitelist."""
    return full_name.strip() in WHITELIST

def calculate_score(student_file_bytes: bytes, solution_path: str = "solution.csv") -> Tuple[Optional[float], Optional[str]]:
    """
    Calculates RMSE between student submission and solution file.
    
    Args:
        student_file_bytes: The byte content of the uploaded CSV.
        solution_path: Path to the ground truth CSV.
        
    Returns:
        Tuple(score, error_message). If success, error_message is None.
    """
    try:
        # Load Solution
        try:
            solution_df = pd.read_csv(solution_path)
        except Exception as e:
            return None, f"Internal Error: Could not load solution file. {str(e)}"

        # Load Submission
        try:
            student_df = pd.read_csv(io.BytesIO(student_file_bytes))
        except Exception as e:
            return None, "خطا در خواندن فایل CSV. لطفا مطمئن شوید فایل سالم است."

        # Basic Validation: Check emptiness
        if student_df.empty:
            return None, "فایل ارسالی خالی است."

        # Logic to align rows. 
        # Case 1: If both have 'id' column, merge on it.
        # Case 2: If no 'id', assume row matching (requiring same length).
        
        # Intersection of numeric columns
        solution_numeric = solution_df.select_dtypes(include=[np.number]).columns
        student_numeric = student_df.select_dtypes(include=[np.number]).columns
        
        # If 'id' is present in both, use it to align
        if 'id' in solution_df.columns.str.lower() and 'id' in student_df.columns.str.lower():
            # Standardize 'id' column name
            solution_df = solution_df.rename(columns={c: 'id' for c in solution_df.columns if c.lower() == 'id'})
            student_df = student_df.rename(columns={c: 'id' for c in student_df.columns if c.lower() == 'id'})
            
            # Merge
            merged = pd.merge(solution_df, student_df, on='id', suffixes=('_true', '_pred'))
            
            # Find the value columns (numeric and not id)
            # Assuming there is only one other numeric column usually, or we take all matching numeric columns
            value_cols = [c for c in solution_numeric if c.lower() != 'id']
            
            if not value_cols:
                 return None, "ستون هدف (Target) در فایل جواب پیدا نشد."
            
            y_true = []
            y_pred = []
            
            for col in value_cols:
                # The student file might have the original name or suffixed if they kept same header
                # After merge, if they had same name 'target', it became 'target_true' and 'target_pred'
                
                # Check if we have col_true and col_pred in merged
                t_col = f"{col}_true"
                p_col = f"{col}_pred"
                
                if t_col in merged.columns and p_col in merged.columns:
                    y_true.extend(merged[t_col].values)
                    y_pred.extend(merged[p_col].values)
                elif col in merged.columns and col in student_df.columns: 
                     # This branch is hard to reach after merge rename, but just in case
                     y_true.extend(merged[col].values) # Wait, this is ambiguous
                     pass
            
            if not y_true:
                # Fallback: Maybe column names didn't match. 
                return None, "نام ستون‌های عددی با فایل جواب مطابقت ندارد."

        else:
            # Case 2: No ID, strict row order
            if len(student_df) != len(solution_df):
                return None, f"تعداد سطرها مطابقت ندارد. انتظار: {len(solution_df)}، دریافت: {len(student_df)}"
            
            common_cols = list(set(solution_numeric) & set(student_numeric))
            if not common_cols:
                 return None, "هیچ ستون مشترک عددی برای ارزیابی یافت نشد."
                 
            y_true = solution_df[common_cols].values.flatten()
            y_pred = student_df[common_cols].values.flatten()

        # Check for NaNs
        if np.isnan(y_pred).any():
            return None, "فایل ارسالی دارای مقادیر خالی (NaN) است."

        rmse = root_mean_squared_error(y_true, y_pred)
        return float(rmse), None

    except Exception as e:
        return None, f"خطای ناشناخته در محاسبه خطا: {str(e)}"
