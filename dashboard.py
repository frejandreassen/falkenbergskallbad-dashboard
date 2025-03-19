import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# Directus API configuration
DIRECTUS_API_URL = st.secrets.get("DIRECTUS_API_URL", "https://cms.falkenbergskallbad.se")
DIRECTUS_API_TOKEN = st.secrets.get("DIRECTUS_API_TOKEN")

# Function to fetch data from Directus
def fetch_from_directus(collection_name):
    """Fetch data from Directus API"""
    headers = {
        "Authorization": f"Bearer {DIRECTUS_API_TOKEN}"
    }
    
    url = f"{DIRECTUS_API_URL}/items/{collection_name}"
    
    # Need to modify our approach based on what endpoint we're hitting
    if collection_name == "bookings":
        # For bookings, we need to expand user and slot, but do it in 
        # a compatible way with the API
        fields = ["*", "user.email", "user.id", "slot.start_time", 
                  "slot.end_time", "slot.description", "slot.available_seats", "slot.id"]
        
        # Filter to include only bookings where end_time is after now
        filter_condition = {
            "slot": {
                "end_time": {
                    "_lte": "$NOW"
                }
            }
        }
        import json  # For JSON encoding
        
        params = {
            "limit": -1,
            "fields": ",".join(fields),
            "filter": json.dumps(filter_condition)
        }
    elif collection_name == "coupons":
        # For coupons, we need user email
        fields = ["*", "user.email", "user.id"]
        params = {
            "limit": -1,
            "fields": ",".join(fields)
        }
    elif collection_name == "slots":
        # For slots, we need to deeply expand bookings.user.email
        fields = ["*", "bookings.user.email", "bookings.id", "bookings.booked_seats"]
        
        # Filter to include only slots where end_time is after now
        filter_condition = {
            "end_time": {
                "_lte": "$NOW"
            }
        }
        import json  # For JSON encoding
        
        params = {
            "limit": -1, 
            "fields": ",".join(fields),
            "filter": json.dumps(filter_condition)
        }
    else:
        # Default case
        params = {
            "limit": -1,
            "fields": "*"
        }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Raise exception for error status codes
        
        data = response.json()["data"]
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Failed to fetch {collection_name} data: {str(e)}")
        return pd.DataFrame()

# Function to load bookings data
@st.cache_data
def load_bookings_data():
    df = fetch_from_directus("bookings")
    if not df.empty:
        try:
            # First, handle the user email for filtering
            user_email_found = False
            
            # Try different ways to extract user email
            if 'user' in df.columns:
                # First check if user is a dict with email
                if isinstance(df['user'].iloc[0], dict) and 'email' in df['user'].iloc[0]:
                    df['user_email'] = df['user'].apply(lambda x: x.get('email') if isinstance(x, dict) else None)
                    user_email_found = True
                # Check if user is an ID
                elif isinstance(df['user'].iloc[0], int) or (isinstance(df['user'].iloc[0], str) and df['user'].iloc[0].isdigit()):
                    pass
            
            elif 'user.email' in df.columns:
                df['user_email'] = df['user.email']
                user_email_found = True
            
            if not user_email_found:
                df['user_email'] = "unknown"
            
            # Filter out specific email if we found emails
            if user_email_found:
                df = df[df['user_email'] != 'frej.andreassen@gmail.com']
            
            # Filter out bookings with status
            if 'status' in df.columns:
                df = df[df['status'].isnull()]
                
        except Exception as e:
            # Continue with unfiltered data rather than failing
            pass
            
    return df

# Function to load Periodkort/klippkort data
@st.cache_data
def load_coupons_data():
    coupons_df = fetch_from_directus("coupons")
    if not coupons_df.empty:
        try:
            # First, handle the user email for filtering
            user_email_found = False
            
            # Try different ways to extract user email
            if 'user' in coupons_df.columns:
                # First check if user is a dict with email
                if isinstance(coupons_df['user'].iloc[0], dict) and 'email' in coupons_df['user'].iloc[0]:
                    coupons_df['user_email'] = coupons_df['user'].apply(lambda x: x.get('email') if isinstance(x, dict) else None)
                    user_email_found = True
                # Check if user is an ID
                elif isinstance(coupons_df['user'].iloc[0], int) or (isinstance(coupons_df['user'].iloc[0], str) and coupons_df['user'].iloc[0].isdigit()):
                    pass
            
            elif 'user.email' in coupons_df.columns:
                coupons_df['user_email'] = coupons_df['user.email']
                user_email_found = True
            
            if not user_email_found:
                coupons_df['user_email'] = "unknown"
                
            # Filter out specific users if we found emails
            if user_email_found:
                excluded_users = ['frej', 'andre', 'oscar', 'charl', 'jenny']
                coupons_df = coupons_df[~coupons_df['user_email'].str.lower().str.contains('|'.join(excluded_users))]
            
        except Exception as e:
            # Continue with unfiltered data rather than failing
            pass
        
    return coupons_df

# Function to load slots data
@st.cache_data
def load_slots_data():
    slots_df = fetch_from_directus("slots")
    return slots_df

# Show a spinner while loading data
with st.spinner("Fetching data from Directus..."):
    # Check if API token is available
    if not DIRECTUS_API_TOKEN:
        st.error("Directus API token not found. Please set the DIRECTUS_API_TOKEN in .streamlit/secrets.toml file.")
        st.stop()
    
    # Load data
    df = load_bookings_data()
    coupons_df = load_coupons_data()
    slots_df = load_slots_data()
    
    # Verify data was loaded
    if df.empty or coupons_df.empty or slots_df.empty:
        st.error("Failed to load data from Directus. Please check your API credentials and connection.")
        st.stop()

# Add logo and title
col1, col2 = st.columns([1, 4])
with col1:
    st.image("https://cms.falkenbergskallbad.se/assets/ff137a4a-f3c0-42f2-a241-c490f6d2fb1d", width=120)
with col2:
    st.title("Falkenbergs Kallbad Boknings Dashboard") # Swedish title
    st.markdown("En dashboard för att visualisera bokningsdata för en bastu.")

# Attempt to process the data based on the fields we have
try:
    # Data Cleaning and Preprocessing for bookings
    if 'date_created' in df.columns:
        df['date_created'] = pd.to_datetime(df['date_created'])
    
    # Try to handle slot data, with better error handling
    slot_fields_found = False
    try:
        # First try the direct dot notation fields
        dot_fields = [field for field in df.columns if '.' in field]
        
        # Check for slot property
        if 'slot' in df.columns and len(df) > 0:
            slot_sample = df['slot'].iloc[0]
            
            # Try to expand slot details
            if isinstance(slot_sample, dict):                
                # Process expanded slot immediately if it has the fields we need
                if 'start_time' in slot_sample and 'end_time' in slot_sample:
                    df['slot_start_time'] = df['slot'].apply(lambda x: x.get('start_time') if isinstance(x, dict) else None)
                    df['slot_end_time'] = df['slot'].apply(lambda x: x.get('end_time') if isinstance(x, dict) else None)
                    df['slot_description'] = df['slot'].apply(lambda x: x.get('description', '') if isinstance(x, dict) else '')
                    slot_fields_found = True
            elif isinstance(slot_sample, (int, float, str)):
                # Check if we have the dot notation fields 
                slot_fields = [f for f in dot_fields if f.startswith('slot.')]
        
        # If we haven't processed the slot yet, try dot notation
        if not slot_fields_found and 'slot.start_time' in df.columns and 'slot.end_time' in df.columns:
            df['slot_start_time'] = df['slot.start_time']
            df['slot_end_time'] = df['slot.end_time']
            df['slot_description'] = df['slot.description'] if 'slot.description' in df.columns else ''
            slot_fields_found = True
            
        # If still not found, try our fallback approaches
        if not slot_fields_found and 'slot' in df.columns:            
            # One more attempt with explicit checks
            if isinstance(df['slot'].iloc[0], dict):
                try:
                    # Extract with explicit error handling
                    df['slot_start_time'] = df['slot'].apply(
                        lambda x: pd.to_datetime(x['start_time']) if isinstance(x, dict) and 'start_time' in x else None
                    )
                    df['slot_end_time'] = df['slot'].apply(
                        lambda x: pd.to_datetime(x['end_time']) if isinstance(x, dict) and 'end_time' in x else None
                    )
                    df['slot_description'] = df['slot'].apply(
                        lambda x: x.get('description', '') if isinstance(x, dict) else ''
                    )
                    slot_fields_found = True
                except Exception:
                    pass
                    
        # As a last resort, look for direct fields without the slot prefix
        if not slot_fields_found and all(field in df.columns for field in ['start_time', 'end_time']):
            df['slot_start_time'] = df['start_time']
            df['slot_end_time'] = df['end_time'] 
            df['slot_description'] = df['description'] if 'description' in df.columns else ''
            slot_fields_found = True
            
        if not slot_fields_found:
            st.warning("Could not find slot fields in the data. Will attempt to continue with limited functionality.")
            
            # Create placeholder columns so the dashboard can still run
            # Use date_created as a fallback for visualization
            if 'date_created' in df.columns:
                df['slot_start_time'] = pd.to_datetime(df['date_created'])
                df['slot_end_time'] = pd.to_datetime(df['date_created']) + pd.Timedelta(hours=1)
            else:
                # Last resort - create dummy dates
                df['slot_start_time'] = pd.to_datetime('2024-01-01')
                df['slot_end_time'] = pd.to_datetime('2024-01-01') + pd.Timedelta(hours=1)
                
            df['slot_description'] = 'Unknown'
    except Exception:
        # Create placeholder data to avoid crashing
        df['slot_start_time'] = pd.to_datetime('2024-01-01')
        df['slot_end_time'] = pd.to_datetime('2024-01-01') + pd.Timedelta(hours=1)
        df['slot_description'] = 'Error'
    
    # Convert to datetime
    df['slot_start_time'] = pd.to_datetime(df['slot_start_time'])
    df['slot_end_time'] = pd.to_datetime(df['slot_end_time'])
    
    # Feature Engineering for bookings
    df['month'] = df['slot_start_time'].dt.month
    df['year'] = df['slot_start_time'].dt.year # Extract year for chronological sorting
    df['week'] = df['slot_start_time'].dt.isocalendar().week
    
    # Safer way to handle day names - fallback to English if Swedish locale fails
    try:
        df['day_of_week'] = df['slot_start_time'].dt.day_name(locale='sv_SE') # Try Swedish day names
    except:
        # If Swedish locale fails, use English and manually translate
        eng_to_swedish = {
            'Monday': 'Måndag',
            'Tuesday': 'Tisdag',
            'Wednesday': 'Onsdag',
            'Thursday': 'Torsdag',
            'Friday': 'Fredag',
            'Saturday': 'Lördag',
            'Sunday': 'Söndag'
        }
        df['day_of_week'] = df['slot_start_time'].dt.day_name().map(eng_to_swedish)
    
    df['hour_of_day'] = df['slot_start_time'].dt.hour
    
    # Check if coupon field exists
    if 'coupon' in df.columns:
        df['payment_method'] = df['coupon'].apply(lambda x: 'Periodkort/klippkort' if pd.notna(x) else 'Swish') # Periodkort/klippkort for coupon, Swish otherwise
    else:
        st.warning("Could not find coupon field in the data")
        df['payment_method'] = 'Unknown'
    
    df['slot_length'] = (df['slot_end_time'] - df['slot_start_time']).dt.total_seconds() / 3600 # Slot length in hours
    df['slot_length'] = df['slot_length'].round() # Round slot length to nearest full hour
    df['slot_length_category'] = df['slot_length'].apply(lambda x: f"{int(x)} timme" if x <= 1 else (f"{int(x)} timmar" if x <= 2 else "3+ timmar")) # Categorize slot length
    
    # Data Cleaning and Preprocessing for coupons
    if 'start_date' in coupons_df.columns:
        coupons_df['start_date'] = pd.to_datetime(coupons_df['start_date'])
        coupons_df['month'] = coupons_df['start_date'].dt.month
        coupons_df['year'] = coupons_df['start_date'].dt.year
    
    # Data Cleaning and Preprocessing for slots
    if 'start_time' in slots_df.columns:
        slots_df['start_time'] = pd.to_datetime(slots_df['start_time'])
        slots_df['month'] = slots_df['start_time'].dt.month
        slots_df['year'] = slots_df['start_time'].dt.year
    
    # Each slot has 10 seats capacity
    slots_df['total_capacity'] = 10
    if 'available_seats' in slots_df.columns:
        slots_df['used_seats'] = 10 - slots_df['available_seats']
    else:
        st.warning("Could not find available_seats in slots data")
        slots_df['used_seats'] = 0  # Default
    
    # Get latest booking date for reference
    latest_booking_date = df['slot_start_time'].max().strftime('%Y-%m-%d')
    st.info(f"Analys uppdaterad till: {latest_booking_date}")
    
    # Summary Section
    st.header("Sammanfattning")
    
    # Calculate key metrics
    total_bookings = len(df)
    if 'booked_seats' in df.columns:
        total_booked_seats = df['booked_seats'].sum()
    else:
        st.warning("Could not find booked_seats in bookings data")
        total_booked_seats = total_bookings  # Assume 1 seat per booking as fallback
    
    total_capacity = slots_df['total_capacity'].sum()
    total_used_seats = slots_df['used_seats'].sum()
    total_utilization = round((total_used_seats / total_capacity) * 100, 2) if total_capacity > 0 else 0
    
    # Find most popular attributes
    most_popular_day = df['day_of_week'].value_counts().index[0] if not df['day_of_week'].empty else "N/A"
    most_popular_hour = df['hour_of_day'].value_counts().index[0] if not df['hour_of_day'].empty else "N/A"
    most_common_length = df['slot_length_category'].value_counts().index[0] if not df['slot_length_category'].empty else "N/A"
    
    # Calculate payment method percentages
    payment_counts = df['payment_method'].value_counts()
    kort_percentage = round((payment_counts.get('Periodkort/klippkort', 0) / total_bookings) * 100, 1) if total_bookings > 0 else 0
    
    # Calculate full bookings (10 seats)
    if 'booked_seats' in df.columns:
        full_sauna_bookings = df[df['booked_seats'] == 10].shape[0]
    else:
        full_sauna_bookings = 0
    full_sauna_percentage = round((full_sauna_bookings / total_bookings) * 100, 1) if total_bookings > 0 else 0
    
    # Calculate seats in full bookings
    seats_in_full_bookings = full_sauna_bookings * 10
    seats_in_full_percentage = round((seats_in_full_bookings / total_booked_seats) * 100, 1) if total_booked_seats > 0 else 0
    
    # Display metrics in columns
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Totalt antal bokningar", f"{total_bookings}")
        st.metric("Fullbokade bastusessioner", f"{full_sauna_bookings} ({full_sauna_percentage}%)")
    with col2:
        st.metric("Totalt bokade platser", f"{total_booked_seats}")
        st.metric("Andel platser i fullbokningar", f"{seats_in_full_bookings} ({seats_in_full_percentage}%)")
    with col3:
        st.metric("Total beläggning", f"{total_utilization}%")
        st.metric("Bokningar med Periodkort/klippkort", f"{kort_percentage}%")
    
    # Additional insights
    with st.expander("Mer information"):
        st.write(f"Populäraste tiden: {most_popular_hour}:00")
        st.write(f"Vanligaste bokningslängd: {most_common_length}")
        st.write(f"Totalt antal platser i systemet: {total_capacity}")
    
    # Bookings by Month - Chronological
    st.header("Bokningar per månad")
    if 'booked_seats' in df.columns:
        monthly_bookings = df.groupby(['year', 'month'])['booked_seats'].sum().reset_index()
    else:
        # If no booked_seats, count bookings instead
        monthly_bookings = df.groupby(['year', 'month']).size().reset_index(name='booked_seats')
    
    # Swedish month names - independent of locale
    swedish_months = {
        1: 'Januari',
        2: 'Februari',
        3: 'Mars',
        4: 'April',
        5: 'Maj',
        6: 'Juni',
        7: 'Juli',
        8: 'Augusti',
        9: 'September',
        10: 'Oktober',
        11: 'November',
        12: 'December'
    }
    
    monthly_bookings['month_name'] = monthly_bookings['month'].map(swedish_months)
    monthly_bookings['month_year'] = monthly_bookings['month_name'] + ' ' + monthly_bookings['year'].astype(str)
    monthly_bookings['month_order'] = monthly_bookings['year'] * 12 + monthly_bookings['month'] # For chronological sorting
    
    # Filter to start from December 2024
    monthly_bookings = monthly_bookings[(monthly_bookings['year'] > 2024) | 
                                   ((monthly_bookings['year'] == 2024) & (monthly_bookings['month'] >= 12))]
    monthly_bookings = monthly_bookings.sort_values('month_order')
    
    
    fig_month = px.bar(monthly_bookings, x='month_year', y='booked_seats',
                 labels={'month_year': 'Månad', 'booked_seats': 'Antal bokningar'},
                 title='Antal bokningar per månad')
    st.plotly_chart(fig_month)
    
    # Bookings by Week - Chronological
    st.header("Bokningar per vecka")
    # Filter data to start from December 2024
    df_filtered = df[(df['year'] > 2024) | ((df['year'] == 2024) & (df['month'] >= 12))]
    
    if 'booked_seats' in df.columns:
        weekly_bookings = df_filtered.groupby(['year', 'week'])['booked_seats'].sum().reset_index()
    else:
        weekly_bookings = df_filtered.groupby(['year', 'week']).size().reset_index(name='booked_seats')
    
    weekly_bookings['week_year'] = 'Vecka ' + weekly_bookings['week'].astype(str) + ', ' + weekly_bookings['year'].astype(str)
    weekly_bookings['week_order'] = weekly_bookings['year'] * 52 + weekly_bookings['week'] # Approximate week order
    weekly_bookings = weekly_bookings.sort_values('week_order')
    
    
    fig_week = px.bar(weekly_bookings, x='week_year', y='booked_seats',
                 labels={'week_year': 'Vecka', 'booked_seats': 'Antal bokningar'},
                 title='Antal bokningar per vecka')
    st.plotly_chart(fig_week)
    
    
    # Bookings by Time of Day, colored by slot length
    st.header("Bokningar per tid på dagen")
    if 'booked_seats' in df.columns:
        hourly_bookings = df.groupby(['hour_of_day', 'slot_length_category'])['booked_seats'].sum().reset_index()
    else:
        hourly_bookings = df.groupby(['hour_of_day', 'slot_length_category']).size().reset_index(name='booked_seats')
    
    fig_hour = px.bar(hourly_bookings, x='hour_of_day', y='booked_seats', color='slot_length_category',
                 labels={'hour_of_day': 'Timme på dagen', 'booked_seats': 'Antal bokningar', 'slot_length_category': 'Bokningslängd'},
                 title='Antal bokningar per timme på dagen, färgkodat efter bokningslängd')
    st.plotly_chart(fig_hour)
    
    # Bookings by Day of Week
    st.header("Bokningar per veckodag")
    day_order = ['Måndag', 'Tisdag', 'Onsdag', 'Torsdag', 'Fredag', 'Lördag', 'Söndag']
    
    if 'booked_seats' in df.columns:
        daily_bookings = df.groupby('day_of_week')['booked_seats'].sum().reset_index()
    else:
        daily_bookings = df.groupby('day_of_week').size().reset_index(name='booked_seats')
    
    daily_bookings['day_of_week'] = pd.Categorical(daily_bookings['day_of_week'], categories=day_order, ordered=True)
    daily_bookings = daily_bookings.sort_values('day_of_week')
    
    fig_day = px.bar(daily_bookings, x='day_of_week', y='booked_seats',
                 labels={'day_of_week': 'Veckodag', 'booked_seats': 'Antal bokningar'},
                 title='Antal bokningar per veckodag')
    st.plotly_chart(fig_day)
    
    # Bookings by Description
    st.header("Bokningar per beskrivning")
    if 'slot_description' in df.columns and 'booked_seats' in df.columns:
        description_bookings = df.groupby('slot_description')['booked_seats'].sum().reset_index()
        
        fig_desc = px.bar(description_bookings, x='slot_description', y='booked_seats',
                     labels={'slot_description': 'Beskrivning', 'booked_seats': 'Antal bokningar'},
                     title='Antal bokningar per beskrivning')
        st.plotly_chart(fig_desc)
    
    # Bookings by Slot Length
    st.header("Bokningar per bokningslängd")
    slot_length_bookings = df['slot_length_category'].value_counts().reset_index()
    slot_length_bookings.columns = ['slot_length_category', 'count'] # Rename columns for clarity
    fig_slot_length = px.bar(slot_length_bookings, x='slot_length_category', y='count',
                         labels={'slot_length_category': 'Bokningslängd', 'count': 'Antal bokningar'},
                         title='Antal bokningar per bokningslängd')
    st.plotly_chart(fig_slot_length)
    
    
    # Payment Method Analysis
    st.header("Betalningsmetod")
    payment_method_bookings = df['payment_method'].value_counts().reset_index()
    payment_method_bookings.columns = ['payment_method', 'count']
    fig_payment = px.pie(payment_method_bookings, names='payment_method', values='count',
                         title='Bokningar per betalningsmetod',
                         labels={'payment_method': 'Betalningsmetod', 'count': 'Antal bokningar'})
    st.plotly_chart(fig_payment)
    
    # Periodkort/klippkort Analysis
    st.header("Periodkort/klippkort per typ")
    if 'type' in coupons_df.columns:
        kort_usage = coupons_df.groupby(['type']).size().reset_index(name='count')
        
        fig_kort_type = px.bar(kort_usage, x='type', y='count',
                             labels={'type': 'Korttyp', 'count': 'Antal kort'},
                             title='Antal periodkort/klippkort per typ')
        st.plotly_chart(fig_kort_type)
    
    
    # Utilization Analysis
    st.markdown("---")
    st.header("Utnyttjandegrad Analys")
    
    # Enhanced data preparation for slots data
    try:
        # Ensure slots_df has the required columns with appropriate types
        if 'year' not in slots_df.columns or 'month' not in slots_df.columns:
            if 'start_time' in slots_df.columns:
                slots_df['start_time'] = pd.to_datetime(slots_df['start_time'], errors='coerce')
                slots_df['year'] = slots_df['start_time'].dt.year
                slots_df['month'] = slots_df['start_time'].dt.month
            else:
                slots_df['year'] = 2024
                slots_df['month'] = 1
        
        # Ensure numeric types for aggregation
        slots_df['year'] = pd.to_numeric(slots_df['year'], errors='coerce').fillna(2024).astype(int)
        slots_df['month'] = pd.to_numeric(slots_df['month'], errors='coerce').fillna(1).astype(int)
        slots_df['total_capacity'] = pd.to_numeric(slots_df['total_capacity'], errors='coerce').fillna(10)
        slots_df['used_seats'] = pd.to_numeric(slots_df['used_seats'], errors='coerce').fillna(0)
        
        # Process bookings data if it exists
        if 'bookings' in slots_df.columns and 'used_seats' not in slots_df.columns:
            # Function to safely count booked seats
            def count_booked_seats(bookings):
                if not isinstance(bookings, list) or len(bookings) == 0:
                    return 0
                total = 0
                for booking in bookings:
                    if isinstance(booking, dict) and 'booked_seats' in booking:
                        try:
                            if isinstance(booking['booked_seats'], (int, float)):
                                total += booking['booked_seats']
                        except:
                            pass
                return total
                
            slots_df['used_seats'] = slots_df['bookings'].apply(count_booked_seats)
        
        # Calculate monthly utilization
        monthly_slots = slots_df.groupby(['year', 'month']).agg(
            total_capacity=('total_capacity', 'sum'),
            used_seats=('used_seats', 'sum')
        ).reset_index()
        
        # Calculate unused seats
        monthly_slots['unused_seats'] = monthly_slots['total_capacity'] - monthly_slots['used_seats']
        
        # Calculate utilization rate safely
        monthly_slots['utilization_rate'] = monthly_slots.apply(
            lambda row: (row['used_seats'] / row['total_capacity'] * 100).round(2) 
            if row['total_capacity'] > 0 else 0, 
            axis=1
        )
    except Exception as e:
        st.error(f"Error in utilization calculations: {str(e)}")
        
        # Create fallback dataframe
        monthly_slots = pd.DataFrame({
            'year': [2024, 2025],
            'month': [12, 1],
            'total_capacity': [100, 100],
            'used_seats': [50, 60],
            'unused_seats': [50, 40],
            'utilization_rate': [50, 60]
        })
    
    # Format for display - using Swedish month names
    monthly_slots['month_name'] = monthly_slots['month'].map(swedish_months)  # Reuse swedish_months dictionary defined earlier
    monthly_slots['month_year'] = monthly_slots['month_name'] + ' ' + monthly_slots['year'].astype(str)
    monthly_slots['month_order'] = monthly_slots['year'] * 12 + monthly_slots['month']
    
    # Filter to start from December 2024
    monthly_slots = monthly_slots[(monthly_slots['year'] > 2024) | 
                                 ((monthly_slots['year'] == 2024) & (monthly_slots['month'] >= 12))]
    monthly_slots = monthly_slots.sort_values('month_order')
    
    # Create stacked bar visualization
    fig_monthly_utilization = px.bar(
        monthly_slots, 
        x='month_year', 
        y=['used_seats', 'unused_seats'],
        labels={
            'month_year': 'Månad', 
            'value': 'Antal Platser', 
            'variable': 'Typ',
            'used_seats': 'Bokade platser',
            'unused_seats': 'Lediga platser'
        },
        title='Använda och Lediga Platser per Månad',
        barmode='stack',
        color_discrete_map={'used_seats': '#1f77b4', 'unused_seats': '#e5e5e5'}
    )
    st.plotly_chart(fig_monthly_utilization)
    
    # Show utilization rate as line chart
    fig_utilization_rate = px.line(
        monthly_slots,
        x='month_year',
        y='utilization_rate',
        labels={'month_year': 'Månad', 'utilization_rate': 'Utnyttjandegrad (%)'},
        title='Utnyttjandegrad per månad (%)',
        markers=True
    )
    st.plotly_chart(fig_utilization_rate)
    
    # Display the utilization data
    st.write(monthly_slots[['month_year', 'total_capacity', 'used_seats', 'utilization_rate']])
    
    # Overall Utilization Rate
    st.subheader("Total Utnyttjandegrad")
    
    # Calculate totals based on slots data
    total_capacity = slots_df['total_capacity'].sum()
    total_used_seats = slots_df['used_seats'].sum()
    
    # Calculate overall utilization rate
    overall_utilization_rate = (total_used_seats / total_capacity) * 100 if total_capacity > 0 else 0
    
    # Display metrics in columns
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Total utnyttjandegrad (%)", value=f"{overall_utilization_rate:.2f}%")
    with col2:
        st.metric(label="Totalt använda platser", value=f"{total_used_seats}")
    with col3:
        st.metric(label="Total kapacitet", value=f"{total_capacity}")

except Exception as e:
    st.error(f"An error occurred while processing the data: {str(e)}")

st.markdown("---")
st.markdown("Data hämtad från Directus API: cms.falkenbergskallbad.se")