import streamlit as st
import pandas as pd
from PyPDF2 import PdfMerger
from pathlib import Path
import io
from auth import SessionManager
from config.database import ActivityLogger


def show():
    """
    MRP Label PDF Merger Module
    Allows merging multiple product label PDFs based on Excel quantity data.
    """

    # === Access Control ===
    SessionManager.require_module_access('mrp_label_generator')

    # Get current user
    user = SessionManager.get_user()
    profile = SessionManager.get_user_profile()

    # === UI HEADER ===
    st.title("📄 MRP Label PDF Merger")
    st.markdown("Upload an Excel file to merge MRP label PDFs based on quantities")
    st.markdown("---")

    # === FILE UPLOAD ===
    uploaded_file = st.file_uploader("Choose an Excel file (.xlsx)", type=['xlsx'])

    if uploaded_file is not None:
        try:
            excel_file = pd.ExcelFile(uploaded_file)

            # Validate sheet
            if "Item Summary" not in excel_file.sheet_names:
                st.error("❌ Error: Sheet 'Item Summary' not found in the Excel file!")
                st.info(f"Available sheets: {', '.join(excel_file.sheet_names)}")
                return

            # Load data
            df = pd.read_excel(uploaded_file, sheet_name="Item Summary")

            # Normalize column names
            column_mapping = {col.lower().strip(): col for col in df.columns}
            required_columns_lower = ["item id", "variation id", "quantity"]
            required_columns_display = ["Item ID", "Variation ID", "Quantity"]

            missing_columns = []
            column_map = {}

            for req_col_lower, req_col_display in zip(required_columns_lower, required_columns_display):
                if req_col_lower in column_mapping:
                    column_map[req_col_display] = column_mapping[req_col_lower]
                else:
                    missing_columns.append(req_col_display)

            if missing_columns:
                st.error(f"❌ Missing required columns: {', '.join(missing_columns)}")
                st.info(f"Available columns: {', '.join(df.columns.tolist())}")
                return

            # Standardize column names
            df = df.rename(columns={
                column_map["Item ID"]: "Item ID",
                column_map["Variation ID"]: "Variation ID",
                column_map["Quantity"]: "quantity"
            })

            # Remove empty rows
            df = df.dropna(subset=["Item ID", "Variation ID", "quantity"], how='all')

            # === PROCESS BUTTON ===
            if st.button("🚀 Process and Merge PDFs", type="primary"):
                with st.spinner("Processing PDFs..."):
                    merger = PdfMerger()
                    total_pages = 0
                    processed_items = 0
                    missing_pdfs = []
                    errors = []

                    label_folder = Path("mrp_label")

                    if not label_folder.exists():
                        st.error("❌ Error: 'mrp_label' folder not found in the current directory!")
                        return

                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    for idx, row in df.iterrows():
                        try:
                            item_id = row["Item ID"]
                            variation_id = row["Variation ID"]
                            quantity = row["quantity"]

                            if pd.isna(quantity) or quantity <= 0:
                                continue

                            quantity = int(quantity)

                            # Use Variation ID if available, else Item ID
                            use_id = int(variation_id) if pd.notna(variation_id) and variation_id != 0 else int(item_id)

                            pdf_path = label_folder / f"{use_id}.pdf"

                            if not pdf_path.exists():
                                missing_pdfs.append(use_id)
                                continue

                            for _ in range(quantity):
                                merger.append(str(pdf_path))
                                total_pages += 1

                            processed_items += 1

                        except Exception as e:
                            errors.append(f"Row {idx + 2}: {str(e)}")

                        progress = (idx + 1) / len(df)
                        progress_bar.progress(progress)
                        status_text.text(f"Processing: {idx + 1}/{len(df)} rows")

                    progress_bar.empty()
                    status_text.empty()

                    excel_filename = uploaded_file.name.replace('.xlsx', '')
                    output_filename = f"mrp_labels_{excel_filename}.pdf"

                    pdf_bytes = io.BytesIO()
                    merger.write(pdf_bytes)
                    merger.close()
                    pdf_bytes.seek(0)

                    # === Display Results ===
                    st.success("✅ Processing Complete!")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Items Processed", processed_items)
                    with col2:
                        st.metric("Total Pages", total_pages)
                    with col3:
                        st.metric("Missing PDFs", len(missing_pdfs))

                    if missing_pdfs:
                        st.warning("⚠️ The following Item/Variation IDs were not found:")
                        st.code(", ".join(map(str, missing_pdfs)))

                    if errors:
                        st.error("❌ Errors encountered:")
                        for error in errors:
                            st.text(error)

                    if total_pages > 0:
                        st.download_button(
                            label="📥 Download Merged PDF",
                            data=pdf_bytes,
                            file_name=output_filename,
                            mime="application/pdf",
                            type="primary"
                        )
                        # === Log Success ===
                        ActivityLogger.log(
                            user_id=user['id'],
                            action_type='module_use',
                            module_key='mrp_label_generator',
                            description="Successfully merged MRP label PDFs",
                            metadata={
                                'total_pages': total_pages,
                                'processed_items': processed_items,
                                'missing_pdfs': missing_pdfs
                            }
                        )
                    else:
                        st.warning("⚠️ No PDFs were merged. Please check your data and PDF files.")

        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
            ActivityLogger.log(
                user_id=user['id'],
                action_type='module_error',
                module_key='mrp_label_generator',
                description=f"Error processing file: {str(e)}",
                success=False
            )

    else:
        st.info("👆 Please upload an Excel file to get started")
        with st.expander("📖 Instructions"):
            st.markdown("""
            ### How to use:
            1. **Upload Excel File**: Click the upload button and select your `.xlsx` file  
            2. **Required Sheet**: Must contain a sheet named **Item Summary**  
            3. **Required Columns**:  
               - `Item ID`: Item identifier  
               - `Variation ID`: Variation identifier (use 0 if none)  
               - `Quantity`: Number of copies to merge  
            4. **PDF Files**: Place all PDFs in a folder named `mrp_label`  
            5. **File Names**: Each PDF should be named `{ID}.pdf` (e.g., `7413.pdf`)  
            6. **Logic**:  
               - If Variation ID is `0` or empty → uses Item ID  
               - If Variation ID is nonzero → uses Variation ID  
            7. **Output**:  
               - A single merged PDF: `mrp_labels_{your_excel_filename}.pdf`  
               - Summary of processed, total pages, and missing PDFs
            """)


# === Requirements ===
# streamlit
# pandas
# PyPDF2
# openpyxl
