"""
MRP Label PDF Merger Module
Merges multiple product label PDFs based on Excel quantity data
PDFs are stored in Supabase Storage
"""
import streamlit as st
import pandas as pd
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import io
import zipfile
from datetime import datetime
from auth.session import SessionManager
from config.database import Database, ActivityLogger


def show():
    """Main entry point for MRP Label Generator module"""
    
    # Ensure user has access
    SessionManager.require_module_access('mrp_label_generator')
    
    # Get current user
    user = SessionManager.get_user()
    profile = SessionManager.get_user_profile()
    is_admin = SessionManager.is_admin()
    is_manager = SessionManager.is_manager()
    
    # Module header
    st.markdown("### 🔖 MRP Label Generator")
    st.markdown("Merge MRP label PDFs based on Excel quantity data")
    st.markdown("---")
    
    # Tabs for different functions
    tab1, tab2 = st.tabs(["📊 Generate Labels", "📂 Manage PDF Library"])
    
    with tab1:
        show_label_generator(user, profile)
    
    with tab2:
        if is_admin or is_manager:
            show_pdf_management(user, profile)
        else:
            st.warning("⚠️ PDF management is only available to Admins and Managers")


def show_label_generator(user, profile):
    """Main label generation interface"""
    
    # File upload
    st.markdown("#### 📤 Upload Excel File")
    uploaded_file = st.file_uploader(
        "Choose an Excel file (.xlsx)", 
        type=['xlsx'],
        help="Must contain 'Item Summary' sheet with Item ID, Variation ID, and Quantity columns"
    )
    
    if uploaded_file is not None:
        # Validate file size
        file_size_mb = uploaded_file.size / (1024 * 1024)
        if file_size_mb > 10:
            st.error(f"❌ File too large ({file_size_mb:.1f} MB). Maximum size is 10 MB.")
            return
        
        try:
            # Log file upload
            ActivityLogger.log(
                user_id=user['id'],
                action_type='file_upload',
                module_key='mrp_label_generator',
                description=f"Uploaded Excel file: {uploaded_file.name}",
                metadata={'filename': uploaded_file.name, 'size_mb': round(file_size_mb, 2)}
            )
            
            excel_file = pd.ExcelFile(uploaded_file)
            
            # Validate sheet
            if "Item Summary" not in excel_file.sheet_names:
                st.error("❌ Error: Sheet 'Item Summary' not found in the Excel file!")
                st.info(f"📋 Available sheets: {', '.join(excel_file.sheet_names)}")
                return
            
            # Load data
            df = pd.read_excel(uploaded_file, sheet_name="Item Summary")
            
            # Show preview
            with st.expander("👀 Preview Data"):
                st.dataframe(df.head(10), use_container_width=True)
            
            # Validate and normalize columns
            df_cleaned = validate_and_clean_dataframe(df)
            
            if df_cleaned is None:
                return
            
            # Calculate totals
            total_items = len(df_cleaned)
            total_pages_expected = df_cleaned['quantity'].sum()
            
            # Show summary
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Items", total_items)
            with col2:
                st.metric("Expected Pages", int(total_pages_expected))
            with col3:
                if total_pages_expected > 200:
                    st.metric("File Size", "Large ⚠️", delta="Check")
                else:
                    st.metric("File Size", "Normal ✅")
            
            # Warning for large files
            if total_pages_expected > 200:
                st.warning("⚠️ This will create a large PDF (>200 pages). Processing may take longer.")
            
            # Info about file splitting
            if total_pages_expected > 25:
                num_files = (total_pages_expected + 24) // 25
                st.info(f"📦 Output will be split into {num_files} file(s) of 25 pages each (delivered as zip)")
            
            # Pre-validate PDFs
            st.markdown("---")
            st.markdown("#### 🔍 Validating PDF Availability...")
            
            with st.spinner("Checking PDF library..."):
                available_pdfs, missing_pdfs = check_pdf_availability(df_cleaned)
            
            if missing_pdfs:
                st.warning(f"⚠️ {len(missing_pdfs)} PDF(s) not found in library:")
                st.code(", ".join(map(str, missing_pdfs[:20])))  # Show first 20
                if len(missing_pdfs) > 20:
                    st.caption(f"...and {len(missing_pdfs) - 20} more")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🚀 Proceed Anyway", type="secondary"):
                        process_and_merge_pdfs(df_cleaned, uploaded_file.name, user, available_pdfs)
                with col2:
                    st.info("💡 Upload missing PDFs in 'Manage PDF Library' tab")
            else:
                st.success(f"✅ All {len(available_pdfs)} required PDFs found in library!")
                
                # Process button
                if st.button("🚀 Generate Merged PDF", type="primary"):
                    process_and_merge_pdfs(df_cleaned, uploaded_file.name, user, available_pdfs)
        
        except Exception as e:
            st.error(f"❌ Error processing Excel file: {str(e)}")
            ActivityLogger.log(
                user_id=user['id'],
                action_type='module_error',
                module_key='mrp_label_generator',
                description=f"Error processing Excel: {str(e)}",
                success=False
            )
    
    else:
        st.info("👆 Please upload an Excel file to get started")
        
        with st.expander("📖 How to Use"):
            st.markdown("""
            ### Instructions:
            
            **1. Prepare Excel File:**
            - Must contain sheet named **"Item Summary"**
            - Required columns: `Item ID`, `Variation ID`, `Quantity`
            
            **2. Column Details:**
            - **Item ID**: Product identifier (numeric)
            - **Variation ID**: Variation identifier (use 0 if none)
            - **Quantity**: Number of label copies needed
            
            **3. PDF Logic:**
            - If Variation ID is **0 or empty** → uses Item ID
            - If Variation ID is **non-zero** → uses Variation ID
            - PDFs must be named: `{ID}.pdf` (e.g., `7413.pdf`)
            
            **4. Output:**
            - PDFs are split into 25-page chunks
            - If >25 pages: Multiple files zipped together (1.pdf, 2.pdf, etc.)
            - If ≤25 pages: Single PDF file
            - Summary of processed items and missing PDFs
            
            **5. PDF Library:**
            - Use "Manage PDF Library" tab to upload/manage PDFs
            - PDFs are stored securely in cloud storage
            - Accessible only to authorized users
            """)


def show_pdf_management(user, profile):
    """PDF library management interface"""
    
    st.markdown("#### 📂 PDF Library Management")
    st.markdown("Upload and manage MRP label PDF files")
    st.markdown("---")
    
    # Get Supabase client
    supabase = Database.get_client()
    
    # Upload section
    st.markdown("##### 📤 Upload PDFs")
    
    uploaded_pdfs = st.file_uploader(
        "Upload PDF files",
        type=['pdf'],
        accept_multiple_files=True,
        help="Upload one or more PDF files. Files should be named with their ID (e.g., 7413.pdf)"
    )
    
    if uploaded_pdfs:
        if st.button("⬆️ Upload Selected PDFs", type="primary"):
            upload_pdfs_to_storage(uploaded_pdfs, user, supabase)
    
    st.markdown("---")
    
    # List existing PDFs
    st.markdown("##### 📋 Current PDF Library")
    
    if st.button("🔄 Refresh List"):
        st.rerun()
    
    try:
        # List files in storage
        response = supabase.storage.from_('mrp_labels').list()
        
        if response:
            pdf_data = []
            for file in response:
                pdf_data.append({
                    'Filename': file['name'],
                    'Size (KB)': round(file['metadata'].get('size', 0) / 1024, 2),
                    'Uploaded': file['created_at'][:10] if 'created_at' in file else 'Unknown'
                })
            
            df_pdfs = pd.DataFrame(pdf_data)
            
            st.write(f"**Total PDFs:** {len(df_pdfs)}")
            st.dataframe(df_pdfs, use_container_width=True, hide_index=True)
            
            # Delete functionality
            st.markdown("---")
            st.markdown("##### 🗑️ Delete PDFs")
            
            pdf_to_delete = st.selectbox(
                "Select PDF to delete",
                options=[f['name'] for f in response]
            )
            
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("🗑️ Delete", type="secondary"):
                    delete_pdf_from_storage(pdf_to_delete, user, supabase)
            
        else:
            st.info("📭 No PDFs in library. Upload some to get started!")
    
    except Exception as e:
        st.error(f"Error accessing PDF library: {str(e)}")


def validate_and_clean_dataframe(df):
    """Validate and clean the input dataframe"""
    
    # Normalize column names (case-insensitive, trim spaces)
    column_mapping = {col.lower().strip(): col for col in df.columns}
    
    # Define column aliases for flexible matching
    column_aliases = {
        'item_id': ['item id', 'itemid', 'item', 'product_id', 'product id'],
        'variation_id': ['variation id', 'variationid', 'variation', 'var_id', 'var id'],
        'quantity': ['quantity', 'qty', 'count', 'copies', 'qnty']
    }
    
    # Find columns
    found_columns = {}
    for standard_name, aliases in column_aliases.items():
        for alias in aliases:
            if alias in column_mapping:
                found_columns[standard_name] = column_mapping[alias]
                break
    
    # Check if all required columns found
    missing = [name for name in ['item_id', 'variation_id', 'quantity'] if name not in found_columns]
    
    if missing:
        st.error(f"❌ Missing required columns: {', '.join(missing)}")
        st.info(f"📋 Available columns: {', '.join(df.columns.tolist())}")
        st.info("💡 Required: Item ID, Variation ID, Quantity (case-insensitive)")
        return None
    
    # Rename columns to standard names
    df_clean = df.rename(columns={
        found_columns['item_id']: 'item_id',
        found_columns['variation_id']: 'variation_id',
        found_columns['quantity']: 'quantity'
    })
    
    # Keep only required columns
    df_clean = df_clean[['item_id', 'variation_id', 'quantity']]
    
    # Remove empty rows
    df_clean = df_clean.dropna(subset=['item_id', 'quantity'], how='all')
    
    # Clean data
    df_clean['variation_id'] = df_clean['variation_id'].fillna(0)
    
    # Validate numeric columns
    try:
        df_clean['item_id'] = pd.to_numeric(df_clean['item_id'], errors='coerce')
        df_clean['variation_id'] = pd.to_numeric(df_clean['variation_id'], errors='coerce')
        df_clean['quantity'] = pd.to_numeric(df_clean['quantity'], errors='coerce')
    except Exception as e:
        st.error(f"❌ Error converting columns to numbers: {str(e)}")
        return None
    
    # Remove invalid rows
    df_clean = df_clean.dropna()
    df_clean = df_clean[df_clean['quantity'] > 0]
    
    # Convert to int
    df_clean['item_id'] = df_clean['item_id'].astype(int)
    df_clean['variation_id'] = df_clean['variation_id'].astype(int)
    df_clean['quantity'] = df_clean['quantity'].astype(int)
    
    if len(df_clean) == 0:
        st.error("❌ No valid data rows found after cleaning")
        return None
    
    return df_clean


def check_pdf_availability(df):
    """Check which PDFs are available in Supabase Storage"""
    
    supabase = Database.get_client()
    
    try:
        # Get list of files in storage
        response = supabase.storage.from_('mrp_labels').list()
        available_files = {file['name'].replace('.pdf', ''): file['name'] for file in response}
        
        required_pdfs = set()
        missing_pdfs = []
        
        for _, row in df.iterrows():
            # Determine which ID to use
            use_id = int(row['variation_id']) if row['variation_id'] != 0 else int(row['item_id'])
            required_pdfs.add(use_id)
            
            if str(use_id) not in available_files:
                missing_pdfs.append(use_id)
        
        return available_files, sorted(missing_pdfs)
    
    except Exception as e:
        st.error(f"Error checking PDF availability: {str(e)}")
        return {}, []


def split_pdf_into_chunks(merged_pdf_bytes, max_pages_per_file=25):
    """Split a merged PDF into chunks of max_pages_per_file"""
    
    pdf_chunks = []
    reader = PdfReader(io.BytesIO(merged_pdf_bytes))
    total_pages = len(reader.pages)
    
    chunk_num = 1
    current_page = 0
    
    while current_page < total_pages:
        writer = PdfWriter()
        pages_in_chunk = 0
        
        # Add up to max_pages_per_file pages to this chunk
        while pages_in_chunk < max_pages_per_file and current_page < total_pages:
            writer.add_page(reader.pages[current_page])
            pages_in_chunk += 1
            current_page += 1
        
        # Write chunk to bytes
        chunk_bytes = io.BytesIO()
        writer.write(chunk_bytes)
        chunk_bytes.seek(0)
        
        pdf_chunks.append({
            'filename': f"{chunk_num}.pdf",
            'data': chunk_bytes.getvalue(),
            'pages': pages_in_chunk
        })
        
        chunk_num += 1
    
    return pdf_chunks


def process_and_merge_pdfs(df, excel_filename, user, available_pdfs):
    """Process the dataframe and merge PDFs"""
    
    supabase = Database.get_client()
    
    with st.spinner("🔄 Processing and merging PDFs..."):
        merger = PdfMerger()
        total_pages = 0
        processed_items = 0
        missing_pdfs = []
        errors = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, row in df.iterrows():
            try:
                item_id = int(row['item_id'])
                variation_id = int(row['variation_id'])
                quantity = int(row['quantity'])
                
                # Determine which ID to use
                use_id = variation_id if variation_id != 0 else item_id
                pdf_filename = f"{use_id}.pdf"
                
                # Check if PDF is available
                if str(use_id) not in available_pdfs:
                    missing_pdfs.append(use_id)
                    continue
                
                # Download PDF from Supabase Storage
                try:
                    pdf_bytes = supabase.storage.from_('mrp_labels').download(pdf_filename)
                    pdf_stream = io.BytesIO(pdf_bytes)
                    
                    # Append to merger multiple times based on quantity
                    for _ in range(quantity):
                        merger.append(pdf_stream)
                        pdf_stream.seek(0)  # Reset stream position
                        total_pages += 1
                    
                    processed_items += 1
                
                except Exception as e:
                    errors.append(f"Error with PDF {use_id}: {str(e)}")
            
            except Exception as e:
                errors.append(f"Row {idx + 2}: {str(e)}")
            
            # Update progress
            progress = (idx + 1) / len(df)
            progress_bar.progress(progress)
            status_text.text(f"Processing: {idx + 1}/{len(df)} items")
        
        progress_bar.empty()
        status_text.empty()
        
        # Generate base filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_basename = excel_filename.replace('.xlsx', '').replace('.xls', '')
        base_filename = f"mrp_labels_{excel_basename}_{timestamp}"
        
        # Process merged PDF
        if total_pages > 0:
            # Write complete merged PDF to bytes
            complete_pdf = io.BytesIO()
            merger.write(complete_pdf)
            merger.close()
            complete_pdf.seek(0)
            complete_pdf_bytes = complete_pdf.getvalue()
            
            # Split into chunks if needed
            if total_pages > 25:
                status_text.text("📦 Splitting PDF into chunks...")
                pdf_chunks = split_pdf_into_chunks(complete_pdf_bytes, max_pages_per_file=25)
                
                # Create zip file
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for chunk in pdf_chunks:
                        zip_file.writestr(chunk['filename'], chunk['data'])
                
                zip_buffer.seek(0)
                download_data = zip_buffer.getvalue()
                download_filename = f"{base_filename}.zip"
                download_mime = "application/zip"
                num_files = len(pdf_chunks)
                total_size_mb = len(download_data) / (1024 * 1024)
                
                status_text.empty()
            else:
                # Single file
                download_data = complete_pdf_bytes
                download_filename = f"{base_filename}.pdf"
                download_mime = "application/pdf"
                num_files = 1
                total_size_mb = len(download_data) / (1024 * 1024)
            
            # Display results
            st.success("✅ Processing Complete!")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Items Processed", processed_items)
            with col2:
                st.metric("Total Pages", total_pages)
            with col3:
                st.metric("Files Created", num_files)
            with col4:
                st.metric("Missing PDFs", len(set(missing_pdfs)))
            with col5:
                st.metric("File Size", f"{total_size_mb:.1f} MB")
            
            if missing_pdfs:
                with st.expander(f"⚠️ {len(set(missing_pdfs))} Missing PDF(s)"):
                    st.code(", ".join(map(str, sorted(set(missing_pdfs)))))
            
            if errors:
                with st.expander(f"❌ {len(errors)} Error(s)"):
                    for error in errors:
                        st.text(error)
            
            # Download button
            download_label = "📥 Download PDF" if num_files == 1 else f"📥 Download Zip ({num_files} PDFs)"
            st.download_button(
                label=download_label,
                data=download_data,
                file_name=download_filename,
                mime=download_mime,
                type="primary"
            )
            
            # Log success
            ActivityLogger.log(
                user_id=user['id'],
                action_type='pdf_generation',
                module_key='mrp_label_generator',
                description=f"Successfully merged {total_pages} MRP labels into {num_files} file(s)",
                metadata={
                    'total_pages': total_pages,
                    'processed_items': processed_items,
                    'num_files': num_files,
                    'missing_pdfs': len(set(missing_pdfs)),
                    'file_size_mb': round(total_size_mb, 2),
                    'output_filename': download_filename
                }
            )
        else:
            st.warning("⚠️ No PDFs were merged. Please check your data and PDF library.")
            merger.close()


def upload_pdfs_to_storage(uploaded_files, user, supabase):
    """Upload PDFs to Supabase Storage"""
    
    success_count = 0
    error_count = 0
    errors = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, uploaded_file in enumerate(uploaded_files):
        try:
            status_text.text(f"Uploading: {uploaded_file.name}")
            
            # Validate filename
            if not uploaded_file.name.lower().endswith('.pdf'):
                errors.append(f"{uploaded_file.name}: Not a PDF file")
                error_count += 1
                continue
            
            # Validate file size (max 50MB)
            file_size_mb = uploaded_file.size / (1024 * 1024)
            if file_size_mb > 50:
                errors.append(f"{uploaded_file.name}: File too large ({file_size_mb:.1f} MB)")
                error_count += 1
                continue
            
            # Upload to Supabase Storage
            file_bytes = uploaded_file.read()
            supabase.storage.from_('mrp_labels').upload(
                uploaded_file.name,
                file_bytes,
                file_options={"content-type": "application/pdf"}
            )
            
            success_count += 1
        
        except Exception as e:
            error_msg = str(e)
            if "already exists" in error_msg.lower():
                errors.append(f"{uploaded_file.name}: Already exists (use delete first)")
            else:
                errors.append(f"{uploaded_file.name}: {error_msg}")
            error_count += 1
        
        progress = (idx + 1) / len(uploaded_files)
        progress_bar.progress(progress)
    
    progress_bar.empty()
    status_text.empty()
    
    # Show results
    if success_count > 0:
        st.success(f"✅ Successfully uploaded {success_count} PDF(s)")
        
        # Log upload
        ActivityLogger.log(
            user_id=user['id'],
            action_type='pdf_upload',
            module_key='mrp_label_generator',
            description=f"Uploaded {success_count} PDF(s) to library",
            metadata={'success_count': success_count, 'error_count': error_count}
        )
    
    if errors:
        st.error(f"❌ {error_count} error(s) occurred:")
        for error in errors:
            st.text(f"• {error}")
    
    if success_count > 0:
        st.rerun()


def delete_pdf_from_storage(filename, user, supabase):
    """Delete a PDF from Supabase Storage"""
    
    try:
        supabase.storage.from_('mrp_labels').remove([filename])
        st.success(f"✅ Deleted {filename}")
        
        # Log deletion
        ActivityLogger.log(
            user_id=user['id'],
            action_type='pdf_deletion',
            module_key='mrp_label_generator',
            description=f"Deleted PDF: {filename}",
            metadata={'filename': filename}
        )
        
        st.rerun()
    
    except Exception as e:
        st.error(f"❌ Error deleting {filename}: {str(e)}")
