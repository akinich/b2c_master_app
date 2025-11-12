"""
CSV Utility Functions
Security utilities for safe CSV export

VERSION HISTORY:
1.0.0 - CSV injection protection - 11/12/25
      SECURITY:
      - sanitize_csv_value() prevents CSV formula injection attacks
      - Protects against RCE via Excel/LibreOffice formula execution
"""
import pandas as pd


def sanitize_csv_value(val):
    """
    Prevent CSV injection attacks by sanitizing potentially dangerous values

    CSV injection occurs when cells starting with =, +, -, @, or tab are
    interpreted as formulas by Excel/LibreOffice. Attackers can execute
    arbitrary commands via formulas like: =cmd|'/c calc'!A1

    Args:
        val: Cell value to sanitize

    Returns:
        Sanitized value safe for CSV export

    Security:
        Prefixes dangerous characters with single quote to force text interpretation

    Example:
        >>> sanitize_csv_value("=1+1")
        "'=1+1"
        >>> sanitize_csv_value("Normal text")
        "Normal text"
    """
    # Handle null/nan values
    if pd.isna(val):
        return val

    # Convert to string and strip whitespace
    val = str(val).strip()

    # Check if value starts with dangerous character
    if val and val[0] in ['=', '+', '-', '@', '\t', '\r']:
        # Prefix with single quote to force text interpretation
        return "'" + val

    return val


def sanitize_dataframe_for_csv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sanitize entire DataFrame for safe CSV export

    Args:
        df: DataFrame to sanitize

    Returns:
        Sanitized DataFrame copy (original unchanged)

    Example:
        >>> df = pd.DataFrame({'A': ['=1+1', 'safe'], 'B': ['+cmd', 'text']})
        >>> safe_df = sanitize_dataframe_for_csv(df)
        >>> safe_df.to_csv('output.csv', index=False)
    """
    # Create a copy to avoid modifying original
    df_copy = df.copy()

    # Apply sanitization to all object (string) columns
    for col in df_copy.columns:
        if df_copy[col].dtype == 'object':
            df_copy[col] = df_copy[col].apply(sanitize_csv_value)

    return df_copy
