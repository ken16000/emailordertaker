import streamlit as st
import json
import datetime
from google import genai
from google.genai import types
import typing 
import pandas as pd # Pandasをインポート (st.dataframeで便利に使うため)

# --- 1. Constants and Initial Configuration ---

MODEL_NAME = "gemini-2.5-flash"  # Use a fast model for general processing

# The prompt template instructs Gemini on what to extract and the required output format (JSON).
PROMPT_TEMPLATE = """
Extract the order information from the email body provided below and strictly follow the specified JSON schema for output.
Use null for any item that does not exist.

# Email Body
---
{email_body}
---

# JSON Schema
{{
  "order_id": "string (e.g.: PO-20250901)",
  "order_date": "string (e.g.: 2025-09-01)",
  "customer_name": "string",
  "total_amount": "integer (amount as number only)",
  "delivery_address": "string",
  "items": [
    {{
      "product_name": "string",
      "quantity": "integer",
      "unit_price": "integer"
    }}
  ]
}}
"""

# --- 2. Session State Initialization ---

# Initialize core variables in Streamlit's session_state for persistence across reruns.
if 'orders' not in st.session_state:
    st.session_state.orders = []
if 'GEMINI_API_KEY' not in st.session_state:
    st.session_state.GEMINI_API_KEY = ""
if 'recipient_email' not in st.session_state:
    st.session_state.recipient_email = "relation@example.com" # Default notification email
# Counter for generating unique internal tracking numbers.
if 'internal_tracking_counter' not in st.session_state:
    st.session_state.internal_tracking_counter = 0

# --- 3. Data Saving Function (using Session State) ---

def save_order_to_state(extracted_data: dict) -> typing.Tuple[bool, str]:
    """Saves the extracted order information to the session state and assigns a unique internal tracking number."""
    
    order_id = extracted_data.get('order_id')
    
    # Check for duplicate order ID.
    if any(order['order_id'] == order_id for order in st.session_state.orders):
        st.warning(f"⚠️ **Order ID: {order_id}** already exists in the session.")
        return False, "Not Assigned (Duplicate Order)"
    
    # --- Internal Tracking Number Generation (Unique Auto-Numbering) ---
    st.session_state.internal_tracking_counter += 1
    internal_tracking_number = f"ITN-{st.session_state.internal_tracking_counter:07d}"
    
    # Construct the data record to be saved.
    data_to_save = {
        "order_id": order_id,
        "internal_tracking_number": internal_tracking_number, 
        "order_date": extracted_data.get('order_date'),
        "customer_name": extracted_data.get('customer_name'),
        "total_amount": extracted_data.get('total_amount'),
        "delivery_address": extracted_data.get('delivery_address'),
        "extraction_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "raw_json": extracted_data # Keep the full JSON output
    }
    
    st.session_state.orders.append(data_to_save)
    return True, internal_tracking_number

# --- 4. Gemini Information Extraction Function ---

def extract_order_info(client: genai.Client, email_body: str) -> typing.Optional[dict]:
    """Uses the Gemini model to extract structured order information from raw text."""
    prompt = PROMPT_TEMPLATE.format(email_body=email_body)
    
    config = types.GenerateContentConfig(
        response_mime_type="application/json"
    )

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt],
            config=config
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"Gemini API Extraction Error: {e}")
        return None

# --- 5. Streamlit UI and Main Logic ---

st.set_page_config(layout="wide", page_title="Gemini Order Processing System (Session Save)")
st.title("📧 Gemini Automated Order Processing System (Session Save)")

# --- Sidebar Configuration Area ---
with st.sidebar:
    st.header("🔑 System Configuration")
    
    api_key_input = st.text_input(
        "Gemini API Key", 
        type="password", 
        value=st.session_state.GEMINI_API_KEY,
        key="api_key_input_field"
    )
    
    if st.button("🔑 Apply API Key & Initialize"):
        st.session_state.GEMINI_API_KEY = api_key_input
        if st.session_state.GEMINI_API_KEY:
            try:
                st.session_state['gemini_client'] = genai.Client(api_key=st.session_state.GEMINI_API_KEY)
                st.success("Gemini client initialized successfully.")
            except Exception as e:
                st.error(f"Failed to initialize API Key: {e}")
                st.session_state['gemini_client'] = None
        else:
            st.warning("Please enter the API key.")

    st.markdown("---")
    
    st.subheader("👥 Stakeholder Notification Settings")
    recipient_email_input = st.text_input(
        "Recipient Email Address",
        value=st.session_state.recipient_email,
        key="recipient_email_input_field",
        placeholder="recipient@company.com"
    )
    st.session_state.recipient_email = recipient_email_input
    
    st.markdown("---")
    st.subheader("💡 Sample Order Email")
    st.code("Subject: Order (Order No: PO-20250901)\n...", language='text')

# User Input Area
st.header("1. Enter Email Body")
email_input = st.text_area(
    "Paste the email body containing the order information here:",
    height=300,
    key="email_input",
    value="Subject: Order (Order No: PO-20250901)\n\nTo: XX Trading Co.\n\nThank you for your business. This is Sato from Order Co., Ltd.\nWe would like to place an order as follows:\n\nOrder Date: 2025-09-01\nDelivery Address: Chiyoda-ku, Tokyo, 100-0001\nTotal Amount: 45000\n\n---\nItem: A4 Copy Paper, Quantity: 10, Unit Price: 3000\nItem: Ballpoint Pen Set, Quantity: 5, Unit Price: 3000\n---\n\nThank you for your kind attention.\nFrom: Order Co., Ltd."
)

# Execution Button
if st.button("🚀 Extract & Process Order Information"):
    
    # Pre-execution checks
    if 'gemini_client' not in st.session_state or not st.session_state.get('gemini_client'):
        st.error("❌ Gemini API Key is not set. Please set the API key in the sidebar.")
        st.stop()
    if not email_input:
        st.warning("Please enter the email body.")
        st.stop()
        
    client = st.session_state['gemini_client']
        
    st.header("2. Information Extraction by Gemini")
    
    # --- Extraction Process ---
    with st.spinner("Gemini is analyzing the email body..."):
        extracted_data = extract_order_info(client, email_input)
    
    if extracted_data:
        st.success("✅ Information extraction successful!")
        st.subheader("Extracted Data (JSON)")
        st.json(extracted_data)
        
        # --- Saving to Session State (Generate Internal Number here) ---
        st.header("3. Saving to Session State & Notification")
        
        # Save and get the internal tracking number
        saved_successfully, internal_tracking_number = save_order_to_state(extracted_data)
        
        order_id = extracted_data.get('order_id', 'N/A')

        if saved_successfully:
            st.success(f"💾 **Order ID: {order_id}** order information saved to session. **Internal Tracking No.: {internal_tracking_number}**")
            
            # --- Generate Comprehensive Notification Message ---
            cust_name = extracted_data.get('customer_name', 'N/A')
            total = extracted_data.get('total_amount', 'N/A')
            order_date = extracted_data.get('order_date', 'N/A')
            delivery_address = extracted_data.get('delivery_address', 'N/A')
            recipient = st.session_state.recipient_email
            
            # **すべての抽出情報を含む通知メッセージ**
            notification_message = f"""
            🔔 **[New Order Alert] - Internal Tracking No.: {internal_tracking_number}**
            
            - **Order ID:** **{order_id}**
            - **Customer:** {cust_name}
            - **Order Date:** {order_date}
            - **Total Amount:** **¥{total:,}**
            - **Delivery Address:** {delivery_address}
            - **Notification Recipient (Simulated):** {recipient}
            
            """
            st.info(notification_message)
            
            # --- Display Item Details (All items in JSON) ---
            st.subheader("📦 Item Details")
            items_list = extracted_data.get('items', [])
            
            if items_list:
                df_items = pd.DataFrame(items_list)
                # Calculate subtotal for better display
                if 'quantity' in df_items.columns and 'unit_price' in df_items.columns:
                    df_items['Subtotal'] = df_items['quantity'] * df_items['unit_price']
                
                # Format currency columns
                st.dataframe(
                    df_items,
                    use_container_width=True,
                    column_config={
                        "unit_price": st.column_config.NumberColumn("Unit Price", format="¥%,d"),
                        "Subtotal": st.column_config.NumberColumn("Subtotal", format="¥%,d"),
                    },
                    hide_index=True
                )
            else:
                st.warning("No item details were extracted.")
            
        else:
            # If saving failed (e.g., duplicate order ID)
            notification_message = f"""
            ⚠️ **[Order Processing Skipped]** - **Order ID:** {order_id}
            - **Reason:** Duplicate Order ID found.
            """
            st.warning(notification_message)


# --- 6. Display Data (For Confirmation) ---

st.markdown("---")
st.header("📋 Order History Saved in Session")

if st.session_state.orders:
    # Prepare data for display from the session state list.
    display_data = []
    for order in st.session_state.orders:
        display_data.append({
            "Order ID": order["order_id"],
            "Internal Tracking No.": order["internal_tracking_number"],
            "Order Date": order["order_date"],
            "Customer Name": order["customer_name"],
            "Total Amount": order["total_amount"],
            "Delivery Address": order["delivery_address"], # Add Delivery Address to history view
            "Extraction Time": order["extraction_time"]
        })

    # Reverse the order for chronological display (newest first).
    display_data.reverse()
    
    st.dataframe(
        display_data, 
        use_container_width=True, 
        column_order=("Order ID", "Internal Tracking No.", "Customer Name", "Order Date", "Total Amount", "Delivery Address", "Extraction Time"),
        column_config={
            "Total Amount": st.column_config.NumberColumn("Total Amount", format="¥%,d")
        }
    )
else:
    st.info("No order information has been saved to the session yet.")