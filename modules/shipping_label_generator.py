"""
Shipping Label Generator Module (Template-integrated version)
"""

import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from auth import SessionManager
from config.database import ActivityLogger


# =====================
# MAIN MODULE FUNCTION
# =====================
def show():
    """Main entry point for the module (called by app.py)"""

    # Ensure access control
    SessionManager.require_module_access("shipping_label_generator")

    user = SessionManager.get_user()

    st.markdown("### 🏷️ Shipping Label Generator")
    st.markdown("Upload your order list (Excel/CSV) to generate printable shipping labels (Order # + Customer Name).")
    st.markdown("---")

    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["xlsx", "xls", "csv"],
        help="Upload a file containing 'order #' and 'name' columns"
    )

    if uploaded_file:
        try:
            # Load file
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file, engine="openpyxl")

            # Normalize
            df.columns = [col.strip().lower() for col in df.columns]

            required_cols = ["order #", "name"]
            missing_cols = [col for col in required_cols if col not in df.columns]

            if missing_cols:
                st.error(f"Missing required columns: {', '.join(missing_cols)}")
                return

            df["order #"] = df["order #"].astype(str).str.strip()
            df["name"] = df["name"].astype(str).str.strip()
            df = df.drop_duplicates(subset=["order #", "name"], keep="first")

            st.success(f"✅ File uploaded successfully! {len(df)} unique labels found.")
            with st.expander("Preview Data"):
                st.dataframe(df.head(10), use_container_width=True)

            st.markdown("---")
            st.markdown("#### 🧾 Generate Labels")

            if st.button("Generate PDF", type="primary"):
                with st.spinner("Generating labels..."):
                    pdf_data = process_data(df, user)

                    if pdf_data:
                        st.success("Labels generated successfully!")

                        # Log activity
                        ActivityLogger.log(
                            user_id=user["id"],
                            action_type="module_use",
                            module_key="shipping_label_generator",
                            description=f"Generated {len(df)} shipping labels",
                            metadata={"filename": uploaded_file.name, "rows": len(df)}
                        )

                        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                        st.download_button(
                            label="📥 Download PDF",
                            data=pdf_data,
                            file_name=f"labels_{timestamp}.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.error("Processing failed. Please try again.")
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")

            ActivityLogger.log(
                user_id=user["id"],
                action_type="module_error",
                module_key="shipping_label_generator",
                description=f"Error processing file: {str(e)}",
                success=False
            )
    else:
        st.info("👆 Please upload a file to begin.")


# =====================
# PROCESSING LOGIC
# =====================
def process_data(df: pd.DataFrame, user: dict):
    """Main PDF generation logic"""

    try:
        DEFAULT_WIDTH_MM = 50
        DEFAULT_HEIGHT_MM = 30
        FONT_ADJUSTMENT = 2
        MIN_SPACING_RATIO = 0.1
        FONT_NAME = "Courier-Bold"

        def wrap_text_to_width(text, font_name, font_size, max_width):
            words = text.split()
            if not words:
                return [""]
            lines = []
            current_line = words[0]
            for word in words[1:]:
                test_line = f"{current_line} {word}"
                if stringWidth(test_line, font_name, font_size) <= max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            lines.append(current_line)
            return lines

        def find_max_font_size_for_multiline(lines, max_width, max_height, font_name):
            font_size = 1
            while True:
                wrapped_lines = []
                for line in lines:
                    wrapped_lines.extend(wrap_text_to_width(line, font_name, font_size, max_width))
                total_height = len(wrapped_lines) * font_size + (len(wrapped_lines) - 1) * 2
                max_line_width = max(stringWidth(line, font_name, font_size) for line in wrapped_lines)
                if max_line_width > (max_width - 4) or total_height > (max_height - 4):
                    return max(font_size - 1, 1)
                font_size += 1

        def draw_label_pdf(c, order_no, customer_name, width, height):
            order_no_text = f"#{order_no.strip()}"
            customer_name_text = customer_name.strip().upper()

            min_spacing = height * MIN_SPACING_RATIO
            half_height = (height - min_spacing) / 2

            # Order #
            order_lines = [order_no_text]
            order_font_size = find_max_font_size_for_multiline(order_lines, width, half_height, FONT_NAME)
            order_font_size = max(order_font_size - FONT_ADJUSTMENT, 1)
            c.setFont(FONT_NAME, order_font_size)
            wrapped_order = []
            for line in order_lines:
                wrapped_order.extend(wrap_text_to_width(line, FONT_NAME, order_font_size, width))
            total_height_order = len(wrapped_order) * order_font_size + (len(wrapped_order) - 1) * 2
            start_y_order = height - half_height + (half_height - total_height_order) / 2
            for i, line in enumerate(wrapped_order):
                x = (width - stringWidth(line, FONT_NAME, order_font_size)) / 2
                y = start_y_order + (len(wrapped_order) - i - 1) * (order_font_size + 2)
                c.drawString(x, y, line)

            # Divider line
            line_y = half_height + min_spacing / 2
            c.setLineWidth(0.5)
            c.line(2, line_y, width - 2, line_y)

            # Customer Name
            words = customer_name_text.split()
            cust_lines = words if len(words) == 2 else [customer_name_text]
            line_font_sizes = []
            for line in cust_lines:
                max_height_per_line = half_height / len(cust_lines)
                fs = find_max_font_size_for_multiline([line], width, max_height_per_line, FONT_NAME)
                fs = max(fs - FONT_ADJUSTMENT, 1)
                line_font_sizes.append(fs)

            total_height_cust = sum(line_font_sizes) + 2 * (len(cust_lines) - 1)
            start_y_cust = (half_height - total_height_cust) / 2
            for i, line in enumerate(cust_lines):
                fs = line_font_sizes[i]
                c.setFont(FONT_NAME, fs)
                x = (width - stringWidth(line, FONT_NAME, fs)) / 2
                y = start_y_cust + (len(cust_lines) - i - 1) * (fs + 2)
                c.drawString(x, y, line)

        # Create PDF
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=(DEFAULT_WIDTH_MM * mm, DEFAULT_HEIGHT_MM * mm))

        for _, row in df.iterrows():
            draw_label_pdf(c, str(row["order #"]), str(row["name"]), DEFAULT_WIDTH_MM * mm, DEFAULT_HEIGHT_MM * mm)
            c.showPage()

        c.save()
        buffer.seek(0)
        return buffer.getvalue()

    except Exception as e:
        ActivityLogger.log(
            user_id=user["id"],
            action_type="module_error",
            module_key="shipping_label_generator",
            description=f"PDF generation failed: {str(e)}",
            success=False
        )
        return None
