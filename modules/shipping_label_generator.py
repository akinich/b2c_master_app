"""
Shipping Label Generator Module
Generates printable PDF labels with Order # and Customer Name
"""
import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from auth.session import SessionManager
from config.database import ActivityLogger


# =====================
# CONSTANTS
# =====================
DEFAULT_WIDTH_MM = 50
DEFAULT_HEIGHT_MM = 30
FONT_ADJUSTMENT = 2
MIN_SPACING_RATIO = 0.1
MAX_FILE_SIZE_MB = 20
BATCH_SIZE = 500  # Labels per batch

AVAILABLE_FONTS = [
    "Courier-Bold",      # Default
    "Helvetica",
    "Helvetica-Bold",
    "Times-Roman",
    "Times-Bold",
    "Courier"
]


# =====================
# MAIN MODULE FUNCTION
# =====================
def show():
    """Main entry point for Shipping Label Generator module"""
    
    # Ensure access control
    SessionManager.require_module_access("shipping_label_generator")
    
    user = SessionManager.get_user()
    profile = SessionManager.get_user_profile()
    
    # Module header
    st.markdown("### 🏷️ Shipping Label Generator")
    st.markdown("Generate printable shipping labels with Order # and Customer Name")
    st.markdown("---")
    
    # Configuration section
    with st.expander("⚙️ Label Configuration", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Font Settings**")
            selected_font = st.selectbox(
                "Font Style",
                AVAILABLE_FONTS,
                index=0,  # Courier-Bold as default
                help="Choose font for labels"
            )
            font_override = st.slider(
                "Font Size Adjustment",
                min_value=-5,
                max_value=5,
                value=0,
                help="Fine-tune font size (+/- points)"
            )
        
        with col2:
            st.markdown("**Label Dimensions**")
            width_mm = st.number_input(
                "Width (mm)",
                min_value=10,
                max_value=500,
                value=DEFAULT_WIDTH_MM,
                help="Label width in millimeters"
            )
            height_mm = st.number_input(
                "Height (mm)",
                min_value=10,
                max_value=500,
                value=DEFAULT_HEIGHT_MM,
                help="Label height in millimeters"
            )
    
    # File upload section
    st.markdown("#### 📤 Upload File")
    uploaded_file = st.file_uploader(
        "Choose Excel or CSV file",
        type=["xlsx", "xls", "csv"],
        help="File must contain 'order #' and 'name' columns"
    )
    
    if uploaded_file:
        # Validate file size
        file_size_mb = uploaded_file.size / (1024 * 1024)
        
        if file_size_mb > MAX_FILE_SIZE_MB:
            st.error(f"❌ File too large ({file_size_mb:.1f} MB). Maximum size is {MAX_FILE_SIZE_MB} MB.")
            st.info("💡 Tip: Split your file into smaller batches")
            return
        
        try:
            # Log file upload
            ActivityLogger.log(
                user_id=user['id'],
                action_type='file_upload',
                module_key='shipping_label_generator',
                description=f"Uploaded file: {uploaded_file.name}",
                metadata={
                    'filename': uploaded_file.name,
                    'size_mb': round(file_size_mb, 2)
                }
            )
            
            # Load file
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file, engine="openpyxl")
            
            # Normalize column names
            df.columns = [col.strip().lower() for col in df.columns]
            
            # Validate required columns
            required_cols = ["order #", "name"]
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
                st.info(f"📋 Available columns: {', '.join(df.columns.tolist())}")
                return
            
            # Clean data
            df["order #"] = df["order #"].astype(str).str.strip()
            df["name"] = df["name"].astype(str).str.strip()
            
            # Track original count
            total_entries = len(df)
            
            # Remove duplicates (always, as per requirement)
            before_dedup = len(df)
            df = df.drop_duplicates(subset=["order #", "name"], keep="first")
            duplicates_removed = before_dedup - len(df)
            
            # Remove empty rows
            df = df[(df["order #"] != "") & (df["name"] != "")]
            
            # Check for empty dataframe
            if df.empty:
                st.warning("⚠️ No valid data found after cleaning!")
                st.info("Please check your file for valid order numbers and names")
                return
            
            # Success message
            st.success(f"✅ File loaded successfully!")
            
            # Summary statistics
            st.markdown("---")
            st.markdown("#### 📊 Summary")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Entries", total_entries)
            with col2:
                st.metric("Duplicates Removed", duplicates_removed)
            with col3:
                st.metric("Labels to Generate", len(df))
            with col4:
                estimated_pages = len(df)
                st.metric("PDF Pages", estimated_pages)
            
            # Warning for large files
            if len(df) > 500:
                st.warning(f"⚠️ Generating {len(df)} labels. This will be processed in batches for performance.")
            
            # Show preview (1-based index)
            st.markdown("---")
            st.markdown("#### 👀 Data Preview")
            df_preview = df[["order #", "name"]].reset_index(drop=True)
            df_preview.index += 1  # Start from 1
            st.dataframe(df_preview.head(20), use_container_width=True)
            
            if len(df) > 20:
                st.caption(f"Showing first 20 of {len(df)} labels")
            
            # Generate button
            st.markdown("---")
            if st.button("🚀 Generate PDF Labels", type="primary", use_container_width=True):
                generate_labels(
                    df=df,
                    user=user,
                    font_name=selected_font,
                    width_mm=width_mm,
                    height_mm=height_mm,
                    font_override=font_override,
                    filename=uploaded_file.name
                )
        
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")
            
            # Log error
            ActivityLogger.log(
                user_id=user['id'],
                action_type='module_error',
                module_key='shipping_label_generator',
                description=f"Error processing file: {str(e)}",
                metadata={'filename': uploaded_file.name},
                success=False
            )
    
    else:
        st.info("👆 Please upload a file to get started")
        
        # Help section
        with st.expander("📖 How to Use"):
            st.markdown("""
            ### Instructions:
            
            **1. File Format:**
            - Supports Excel (.xlsx, .xls) and CSV files
            - Maximum file size: 20 MB
            - Required columns: `order #` and `name` (case-insensitive)
            
            **2. Label Configuration:**
            - **Font Style:** Choose from 6 available fonts (default: Courier-Bold)
            - **Font Size:** Adjust size by ±5 points if needed
            - **Dimensions:** Customize label size (default: 50mm × 30mm)
            
            **3. Data Processing:**
            - Duplicates are automatically removed
            - Empty rows are filtered out
            - Large files (>500 labels) are processed in batches
            
            **4. Label Format:**
            ```
            #12345
            ─────────────
            CUSTOMER NAME
            ```
            - Order number with # prefix (top)
            - Horizontal divider line
            - Customer name in UPPERCASE (bottom)
            - Names with 2 words split into 2 lines
            
            **5. Output:**
            - One label per PDF page
            - Filename: `labels_YYYYMMDD_HHMM.pdf`
            - Ready to print on label printer
            
            **6. Best Practices:**
            - Test with small file first
            - Verify label dimensions match your printer
            - Check font size on printed sample
            - For >1000 labels, split into multiple files
            """)


# =====================
# LABEL GENERATION
# =====================
def generate_labels(df, user, font_name, width_mm, height_mm, font_override, filename):
    """Generate PDF labels with progress tracking and batching"""
    
    total_labels = len(df)
    
    # Determine if batching is needed
    if total_labels > BATCH_SIZE:
        st.info(f"📦 Processing {total_labels} labels in batches of {BATCH_SIZE}...")
        process_with_batching(df, user, font_name, width_mm, height_mm, font_override, filename)
    else:
        process_single_batch(df, user, font_name, width_mm, height_mm, font_override, filename)


def process_single_batch(df, user, font_name, width_mm, height_mm, font_override, filename):
    """Process all labels in one batch"""
    
    with st.spinner("🔄 Generating labels..."):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            pdf_data = create_pdf_with_progress(
                df, font_name, width_mm, height_mm, font_override, progress_bar, status_text
            )
            
            progress_bar.empty()
            status_text.empty()
            
            if pdf_data:
                st.success(f"✅ Successfully generated {len(df)} labels!")
                
                # Generate filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                output_filename = f"labels_{timestamp}.pdf"
                
                # Calculate file size
                file_size_mb = len(pdf_data) / (1024 * 1024)
                
                # Show metrics
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Labels Generated", len(df))
                with col2:
                    st.metric("PDF Size", f"{file_size_mb:.2f} MB")
                
                # Download button
                st.download_button(
                    label="📥 Download PDF Labels",
                    data=pdf_data,
                    file_name=output_filename,
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )
                
                # Log success
                ActivityLogger.log(
                    user_id=user['id'],
                    action_type='pdf_generation',
                    module_key='shipping_label_generator',
                    description=f"Generated {len(df)} shipping labels",
                    metadata={
                        'label_count': len(df),
                        'font': font_name,
                        'dimensions': f"{width_mm}x{height_mm}mm",
                        'file_size_mb': round(file_size_mb, 2),
                        'output_filename': output_filename
                    }
                )
            else:
                st.error("❌ Failed to generate PDF. Please try again.")
        
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"❌ Error generating PDF: {str(e)}")
            
            ActivityLogger.log(
                user_id=user['id'],
                action_type='module_error',
                module_key='shipping_label_generator',
                description=f"PDF generation failed: {str(e)}",
                success=False
            )


def process_with_batching(df, user, font_name, width_mm, height_mm, font_override, filename):
    """Process large files in batches"""
    
    total_labels = len(df)
    num_batches = (total_labels + BATCH_SIZE - 1) // BATCH_SIZE
    
    st.info(f"📦 Processing {num_batches} batch(es)...")
    
    all_pdfs = []
    overall_progress = st.progress(0)
    batch_status = st.empty()
    
    try:
        for batch_num in range(num_batches):
            start_idx = batch_num * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, total_labels)
            batch_df = df.iloc[start_idx:end_idx]
            
            batch_status.text(f"Processing batch {batch_num + 1}/{num_batches} ({len(batch_df)} labels)...")
            
            # Create PDF for this batch
            pdf_data = create_pdf_simple(batch_df, font_name, width_mm, height_mm, font_override)
            
            if pdf_data:
                all_pdfs.append(pdf_data)
            
            overall_progress.progress((batch_num + 1) / num_batches)
        
        overall_progress.empty()
        batch_status.empty()
        
        if len(all_pdfs) == num_batches:
            st.success(f"✅ Successfully generated {total_labels} labels in {num_batches} batch(es)!")
            
            # Provide download buttons for each batch
            st.markdown("#### 📥 Download Batches")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            
            for i, pdf_data in enumerate(all_pdfs):
                batch_start = i * BATCH_SIZE + 1
                batch_end = min((i + 1) * BATCH_SIZE, total_labels)
                batch_filename = f"labels_{timestamp}_batch{i+1}_({batch_start}-{batch_end}).pdf"
                
                st.download_button(
                    label=f"📥 Batch {i+1}: Labels {batch_start}-{batch_end}",
                    data=pdf_data,
                    file_name=batch_filename,
                    mime="application/pdf",
                    key=f"batch_{i}"
                )
            
            # Log success
            ActivityLogger.log(
                user_id=user['id'],
                action_type='pdf_generation',
                module_key='shipping_label_generator',
                description=f"Generated {total_labels} labels in {num_batches} batches",
                metadata={
                    'label_count': total_labels,
                    'batch_count': num_batches,
                    'font': font_name,
                    'dimensions': f"{width_mm}x{height_mm}mm"
                }
            )
        else:
            st.error("❌ Some batches failed to generate. Please try again.")
    
    except Exception as e:
        overall_progress.empty()
        batch_status.empty()
        st.error(f"❌ Error during batch processing: {str(e)}")


# =====================
# PDF CREATION HELPERS
# =====================
def create_pdf_with_progress(df, font_name, width_mm, height_mm, font_override, progress_bar, status_text):
    """Create PDF with progress updates"""
    
    try:
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=(width_mm * mm, height_mm * mm))
        
        total = len(df)
        
        for idx, row in df.iterrows():
            status_text.text(f"Generating label {idx + 1} of {total}...")
            
            draw_label_pdf(
                c,
                str(row["order #"]),
                str(row["name"]),
                font_name,
                width_mm * mm,
                height_mm * mm,
                font_override
            )
            c.showPage()
            
            progress_bar.progress((idx + 1) / total)
        
        c.save()
        buffer.seek(0)
        return buffer.getvalue()
    
    except Exception as e:
        st.error(f"Error creating PDF: {str(e)}")
        return None


def create_pdf_simple(df, font_name, width_mm, height_mm, font_override):
    """Create PDF without progress updates (for batching)"""
    
    try:
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=(width_mm * mm, height_mm * mm))
        
        for _, row in df.iterrows():
            draw_label_pdf(
                c,
                str(row["order #"]),
                str(row["name"]),
                font_name,
                width_mm * mm,
                height_mm * mm,
                font_override
            )
            c.showPage()
        
        c.save()
        buffer.seek(0)
        return buffer.getvalue()
    
    except Exception as e:
        return None


# =====================
# LABEL DRAWING LOGIC
# =====================
def wrap_text_to_width(text, font_name, font_size, max_width):
    """Wrap text into multiple lines that fit within max_width"""
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
    """Find maximum font size that fits text within dimensions"""
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


def draw_label_pdf(c, order_no, customer_name, font_name, width, height, font_override=0):
    """Draw order number and customer name on PDF label"""
    
    order_no_text = f"#{order_no.strip()}"
    customer_name_text = customer_name.strip().upper()
    
    # Calculate sections
    min_spacing = height * MIN_SPACING_RATIO
    half_height = (height - min_spacing) / 2
    
    # === Order # Section (top) ===
    order_lines = [order_no_text]
    order_font_size = find_max_font_size_for_multiline(order_lines, width, half_height, font_name)
    order_font_size = max(order_font_size - FONT_ADJUSTMENT + font_override, 1)
    
    c.setFont(font_name, order_font_size)
    wrapped_order = []
    for line in order_lines:
        wrapped_order.extend(wrap_text_to_width(line, font_name, order_font_size, width))
    
    total_height_order = len(wrapped_order) * order_font_size + (len(wrapped_order) - 1) * 2
    start_y_order = height - half_height + (half_height - total_height_order) / 2
    
    for i, line in enumerate(wrapped_order):
        x = (width - stringWidth(line, font_name, order_font_size)) / 2
        y = start_y_order + (len(wrapped_order) - i - 1) * (order_font_size + 2)
        c.drawString(x, y, line)
    
    # === Horizontal Line ===
    line_y = half_height + min_spacing / 2
    c.setLineWidth(0.5)
    c.line(2, line_y, width - 2, line_y)
    
    # === Customer Name Section (bottom) ===
    words = customer_name_text.split()
    cust_lines = words if len(words) == 2 else [customer_name_text]
    
    line_font_sizes = []
    for line in cust_lines:
        max_height_per_line = half_height / len(cust_lines)
        fs = find_max_font_size_for_multiline([line], width, max_height_per_line, font_name)
        fs = max(fs - FONT_ADJUSTMENT + font_override, 1)
        line_font_sizes.append(fs)
    
    total_height_cust = sum(line_font_sizes) + 2 * (len(cust_lines) - 1)
    start_y_cust = (half_height - total_height_cust) / 2
    
    for i, line in enumerate(cust_lines):
        fs = line_font_sizes[i]
        c.setFont(font_name, fs)
        x = (width - stringWidth(line, font_name, fs)) / 2
        y = start_y_cust + (len(cust_lines) - i - 1) * (fs + 2)
        c.drawString(x, y, line)
