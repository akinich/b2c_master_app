"""
Template for creating new modules
Copy this file and rename it to match your module_key
Example: order_extractor.py, shipping_label_generator.py, etc.
"""
import streamlit as st
import pandas as pd
from auth import SessionManager
from config.database import ActivityLogger

def show():
    """
    Main entry point for the module
    This function will be called by app.py when the module is accessed
    """
    
    # Ensure user has access to this module
    # Replace 'module_key_here' with your actual module key
    SessionManager.require_module_access('module_key_here')
    
    # Get current user info
    user = SessionManager.get_user()
    profile = SessionManager.get_user_profile()
    
    # Module UI starts here
    st.markdown("### 📦 Your Module Name Here")
    st.markdown("Description of what this module does")
    st.markdown("---")
    
    # Example: File upload
    st.markdown("#### Upload File")
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=['xlsx', 'xls', 'csv'],
        help="Upload your input file"
    )
    
    if uploaded_file:
        try:
            # Process the file
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success(f"File uploaded successfully! Found {len(df)} rows.")
            
            # Display preview
            with st.expander("Preview Data"):
                st.dataframe(df.head(10), use_container_width=True)
            
            # Your processing logic here
            st.markdown("---")
            st.markdown("#### Process Data")
            
            if st.button("Process", type="primary"):
                with st.spinner("Processing..."):
                    # Your processing code here
                    result = process_data(df, user)
                    
                    if result:
                        st.success("Processing completed successfully!")
                        
                        # Log the activity
                        ActivityLogger.log(
                            user_id=user['id'],
                            action_type='module_use',
                            module_key='module_key_here',
                            description="Successfully processed file",
                            metadata={'filename': uploaded_file.name, 'rows': len(df)}
                        )
                        
                        # Provide download option
                        st.download_button(
                            label="📥 Download Result",
                            data=result,
                            file_name="output.pdf",  # or .xlsx, .csv, etc.
                            mime="application/pdf"  # adjust based on output type
                        )
                    else:
                        st.error("Processing failed. Please check your data.")
        
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            
            # Log error
            ActivityLogger.log(
                user_id=user['id'],
                action_type='module_error',
                module_key='module_key_here',
                description=f"Error processing file: {str(e)}",
                success=False
            )
    
    else:
        st.info("👆 Please upload a file to begin")
    
    # Additional module features
    st.markdown("---")
    st.markdown("#### Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        option1 = st.checkbox("Option 1", value=True)
    
    with col2:
        option2 = st.selectbox("Select option", ["Option A", "Option B", "Option C"])
    
    # Help section
    with st.expander("ℹ️ Help & Instructions"):
        st.markdown("""
        ### How to use this module:
        
        1. Upload your input file (Excel or CSV)
        2. Review the data preview
        3. Configure any options if needed
        4. Click 'Process' to generate output
        5. Download the result
        
        **Supported file formats:**
        - Excel (.xlsx, .xls)
        - CSV (.csv)
        
        **Need help?** Contact your administrator.
        """)


def process_data(df: pd.DataFrame, user: dict):
    """
    Your main processing logic goes here
    
    Args:
        df: Input dataframe
        user: Current user info
    
    Returns:
        Processed data (bytes for download, or path to file, etc.)
    """
    # Example processing
    # Replace this with your actual logic
    
    # For Excel output:
    # output = BytesIO()
    # df.to_excel(output, index=False)
    # return output.getvalue()
    
    # For PDF output:
    # return generate_pdf(df)
    
    # For CSV output:
    # return df.to_csv(index=False).encode('utf-8')
    
    # Placeholder
    return b"Processed data here"


# Additional helper functions for your module
def helper_function_1():
    """Helper function example"""
    pass


def helper_function_2():
    """Another helper function"""
    pass
