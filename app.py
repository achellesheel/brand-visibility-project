import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px
import plotly.graph_objects as go

# ----------------------------------------------------
# 1. PAGE CONFIGURATION & STYLING
# ----------------------------------------------------
st.set_page_config(
    page_title="Brand Visibility Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Premium UI Styling using Custom CSS
st.markdown("""
<style>
    /* Metric styling */
    div[data-testid="stMetricValue"] {
        font-size: 24px;
        font-weight: 700;
        color: #1F77B4;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 14px;
        font-weight: 600;
        color: #4A4A4A;
    }
    /* Tab formatting */
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 16px;
        font-weight: bold;
    }
    /* Card design */
    .card {
        background-color: #F8F9FA;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0px;
        border-left: 5px solid #1F77B4;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# 2. DATABASE UTILITIES & CACHED LOADERS
# ----------------------------------------------------
DB_PATH = "brand_visibility.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

@st.cache_data
def fetch_metadata():
    """Fetch initial lists of filter options from database."""
    conn = get_connection()
    keywords = sorted([r[0] for r in conn.execute("SELECT DISTINCT keyword FROM listings WHERE keyword IS NOT NULL AND keyword != ''").fetchall()])
    platforms = sorted([r[0] for r in conn.execute("SELECT DISTINCT platform FROM listings WHERE platform IS NOT NULL AND platform != ''").fetchall()])
    brands = sorted([r[0] for r in conn.execute("SELECT DISTINCT brand FROM listings WHERE brand IS NOT NULL AND brand != ''").fetchall()])
    min_price, max_price = conn.execute("SELECT MIN(price), MAX(price) FROM listings").fetchone()
    min_rating, max_rating = conn.execute("SELECT MIN(rating), MAX(rating) FROM listings").fetchone()
    conn.close()
    
    return {
        "keywords": keywords,
        "platforms": platforms,
        "brands": brands,
        "min_price": float(min_price or 0.0),
        "max_price": float(max_price or 1000.0),
        "min_rating": float(min_rating or 0.0),
        "max_rating": float(max_rating or 5.0)
    }

# Load metadata
meta = fetch_metadata()

# ----------------------------------------------------
# 3. SIDEBAR FILTERS (CONNECTED TO SQL)
# ----------------------------------------------------
st.sidebar.title("📊 Filter Dashboard")
st.sidebar.markdown("Filters dynamically query the database.")

# Keywords
selected_keywords = st.sidebar.multiselect(
    "Keywords",
    options=meta["keywords"],
    default=[]
)

# Brands
selected_brands = st.sidebar.multiselect(
    "Brands",
    options=meta["brands"],
    default=[]
)

# Platforms
selected_platforms = st.sidebar.multiselect(
    "Platforms",
    options=meta["platforms"],
    default=[]
)

# Price Range Slider
price_range = st.sidebar.slider(
    "Price Range ($)",
    min_value=meta["min_price"],
    max_value=meta["max_price"],
    value=(meta["min_price"], meta["max_price"]),
    step=1.0
)

# Rating Range Slider
rating_range = st.sidebar.slider(
    "Rating Range (Stars)",
    min_value=0.0,
    max_value=5.0,
    value=(0.0, 5.0),
    step=0.1
)

# Position/Rank Filter
position_range = st.sidebar.slider(
    "Search Position (Rank)",
    min_value=1,
    max_value=120,
    value=(1, 120),
    step=1
)

# Reset Button
if st.sidebar.button("Clear All Filters"):
    st.rerun()

# ----------------------------------------------------
# 4. DATA LOADING & FILTER QUERY ENGINE
# ----------------------------------------------------
def query_filtered_data():
    """Build and execute dynamic SQL query based on filters."""
    # Pre-calculate position (rank) per keyword group based on inserting ID sequence
    base_query = """
    WITH pre_ranked AS (
        SELECT *, 
               ROW_NUMBER() OVER (PARTITION BY keyword ORDER BY id) AS position
        FROM listings
    )
    SELECT * FROM pre_ranked
    """
    
    # We construct the query filtering the pre-ranked rows
    sql = f"SELECT * FROM ({base_query}) AS subquery WHERE 1=1"
    params = []
    
    if selected_keywords:
        sql += " AND keyword IN (" + ",".join(["?"] * len(selected_keywords)) + ")"
        params.extend(selected_keywords)
        
    if selected_brands:
        sql += " AND brand IN (" + ",".join(["?"] * len(selected_brands)) + ")"
        params.extend(selected_brands)
        
    if selected_platforms:
        sql += " AND platform IN (" + ",".join(["?"] * len(selected_platforms)) + ")"
        params.extend(selected_platforms)
        
    # Price filter
    sql += " AND price BETWEEN ? AND ?"
    params.extend([price_range[0], price_range[1]])
    
    # Rating filter
    sql += " AND rating BETWEEN ? AND ?"
    params.extend([rating_range[0], rating_range[1]])
    
    # Position (Rank) filter
    sql += " AND position BETWEEN ? AND ?"
    params.extend([position_range[0], position_range[1]])
    
    conn = get_connection()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    
    # Add helper columns
    if not df.empty:
        # Calculate discount
        df['discount'] = df['old_price'] - df['price']
        df['discount_pct'] = np.where(
            (df['old_price'] > df['price']) & (df['old_price'] > 0),
            ((df['old_price'] - df['price']) / df['old_price']) * 100,
            0.0
        )
    else:
        df['discount'] = pd.Series(dtype='float64')
        df['discount_pct'] = pd.Series(dtype='float64')
        
    return df

df = query_filtered_data()

# Check if data is loaded and not empty
if df.empty:
    st.warning("⚠️ No products found matching the selected filter combinations. Please widen your filters.")
    st.stop()

# ----------------------------------------------------
# 5. DASHBOARD LAYOUT & TABS
# ----------------------------------------------------
st.title("🏆 Brand Visibility Analytics Dashboard")
st.markdown("Interactive analytics and visualization tool to monitor product ranking, search engine visibility, pricing models, and brand share.")

tabs = st.tabs([
    "📈 Executive Overview",
    "🏷️ Brand Analysis",
    "💰 Pricing Insights",
    "🏬 Platform Comparison",
    "🎯 Visibility & Ranking",
    "🔍 Product Explorer"
])

# ----------------------------------------------------
# TAB 1: EXECUTIVE OVERVIEW
# ----------------------------------------------------
with tabs[0]:
    st.subheader("Market Summary & High-Level KPIs")
    
    # 5 KPI cards
    kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)
    
    total_products = len(df)
    avg_price = df['price'].mean()
    avg_rating = df['rating'].mean()
    total_reviews = df['reviews'].sum()
    avg_visibility = df['visibility_score'].mean()
    
    kpi_col1.metric("Total Products", f"{total_products:,}")
    kpi_col2.metric("Avg Price", f"${avg_price:,.2f}")
    kpi_col3.metric("Avg Rating", f"{avg_rating:.2f} / 5.0")
    kpi_col4.metric("Total Reviews", f"{total_reviews:,}")
    kpi_col5.metric("Avg Visibility Score", f"{avg_visibility:.2f} pts")
    
    st.markdown("---")
    
    # Grid of Charts (General Market Analysis)
    row1_col1, row1_col2 = st.columns(2)
    
    with row1_col1:
        st.markdown("#### 💵 Product Price Distribution")
        fig_price_dist = px.histogram(
            df, x="price", nbins=40,
            title="Count of Products in Price Intervals",
            labels={"price": "Price ($)"},
            color_discrete_sequence=["#1F77B4"]
        )
        st.plotly_chart(fig_price_dist, use_container_width=True)
        
    with row1_col2:
        st.markdown("#### 📋 Products Available per Keyword")
        keyword_counts = df['keyword'].value_counts().reset_index()
        keyword_counts.columns = ['Keyword', 'Count']
        fig_keyword = px.bar(
            keyword_counts, x="Count", y="Keyword", orientation='h',
            title="Volume of Listed Products by Search Term",
            color="Count", color_continuous_scale="Viridis",
            labels={"Count": "Total Products", "Keyword": "Search Keyword"}
        )
        fig_keyword.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_keyword, use_container_width=True)
        
    # Row 2: 2 columns for Brand Frequency and Platform Share
    row2_col1, row2_col2 = st.columns(2)
    
    with row2_col1:
        st.markdown("#### 🏢 Top 10 Most Frequent Brands")
        brand_counts = df['brand'].value_counts().head(10).reset_index()
        brand_counts.columns = ['Brand', 'Appearances']
        fig_brand_freq = px.bar(
            brand_counts, x="Brand", y="Appearances",
            title="Brands with Highest E-commerce Catalog Representation",
            color="Appearances", color_continuous_scale="Cividis",
            height=450
        )
        st.plotly_chart(fig_brand_freq, use_container_width=True)
        
    with row2_col2:
        st.markdown("#### 🛒 Platform Distribution Share")
        # Group minor platforms to keep the pie chart clean
        top_plats = df['platform'].value_counts().nlargest(8).index
        df_pie = df.copy()
        df_pie['platform_grouped'] = df_pie['platform'].apply(lambda x: x if x in top_plats else 'Other')
        platform_counts = df_pie['platform_grouped'].value_counts().reset_index()
        platform_counts.columns = ['Platform', 'Count']
        fig_platform = px.pie(
            platform_counts, values="Count", names="Platform",
            title="Market Share of Products by Retail Platform (Top 8 + Other)",
            hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel,
            height=450
        )
        st.plotly_chart(fig_platform, use_container_width=True)
        
    # Row 3: Full-width column for Average Rating by Platform to avoid squeezed categories and label overlaps
    st.markdown("---")
    st.markdown("#### ⭐ Average Rating by Platform")
    # Limit to top 15 platforms by count to avoid clutter
    top_plat_names = df['platform'].value_counts().nlargest(15).index
    df_top_plats = df[df['platform'].isin(top_plat_names)]
    plat_ratings = df_top_plats.groupby('platform')['rating'].mean().reset_index()
    plat_ratings.columns = ['Platform', 'Avg Rating']
    plat_ratings = plat_ratings.sort_values(by='Avg Rating', ascending=False)
    fig_plat_rating = px.bar(
        plat_ratings, x="Platform", y="Avg Rating",
        title="Customer Rating Benchmarks across Top Selling Platforms",
        color="Avg Rating", color_continuous_scale="Bluered",
        height=500
    )
    st.plotly_chart(fig_plat_rating, use_container_width=True)

# ----------------------------------------------------
# TAB 2: BRAND ANALYSIS
# ----------------------------------------------------
with tabs[1]:
    st.subheader("Brand Visibility and Ranking Benchmarks")
    
    # Filter out empty or placeholder brands to compute clean KPIs
    df_brand = df[df['brand'].notna() & (df['brand'] != '')]
    
    if df_brand.empty:
        st.info("Please widen filters to show brand-level insights.")
    else:
        # KPIs
        bkpi_col1, bkpi_col2, bkpi_col3, bkpi_col4 = st.columns(4)
        
        total_brands = df_brand['brand'].nunique()
        top_brand_name = df_brand['brand'].value_counts().index[0]
        top_brand_cnt = df_brand['brand'].value_counts().values[0]
        
        # Aggregate brands (with at least 2 listings to avoid outlier single listings)
        brand_agg = df_brand.groupby('brand').agg(
            avg_rating=('rating', 'mean'),
            avg_vis=('visibility_score', 'mean'),
            avg_pos=('position', 'mean'),
            count=('id', 'count')
        ).reset_index()
        
        # Safe filters
        brand_min_filter = brand_agg[brand_agg['count'] >= min(3, len(df_brand))]
        if brand_min_filter.empty:
            brand_min_filter = brand_agg
            
        best_rated_brand = brand_min_filter.sort_values(by='avg_rating', ascending=False).iloc[0]['brand']
        best_rated_val = brand_min_filter.sort_values(by='avg_rating', ascending=False).iloc[0]['avg_rating']
        
        best_vis_brand = brand_min_filter.sort_values(by='avg_vis', ascending=False).iloc[0]['brand']
        best_vis_val = brand_min_filter.sort_values(by='avg_vis', ascending=False).iloc[0]['avg_vis']
        
        bkpi_col1.metric("Total Unique Brands", f"{total_brands}")
        bkpi_col2.metric("Top Brand (by Count)", f"{top_brand_name} ({top_brand_cnt})")
        bkpi_col3.metric("Highest Rated Brand", f"{best_rated_brand} ({best_rated_val:.2f}⭐)")
        bkpi_col4.metric("Best Visibility Brand", f"{best_vis_brand} ({best_vis_val:.1f} pts)")
        
        st.markdown("---")
        
        # Charts
        col2_1, col2_2 = st.columns(2)
        
        with col2_1:
            st.markdown("#### 📊 Brand Volume Market Share (Top 20)")
            top_20_brands = brand_agg.sort_values(by='count', ascending=False).head(20)
            fig_brand_count = px.bar(
                top_20_brands, x="brand", y="count",
                title="Number of Products Offered by Brand",
                color="count", color_continuous_scale="teal"
            )
            st.plotly_chart(fig_brand_count, use_container_width=True)
            
        with col2_2:
            st.markdown("#### 🌟 Average Rating by Brand (Min 3 Listings)")
            top_rated_brands_plot = brand_min_filter.sort_values(by='avg_rating', ascending=False).head(20)
            fig_brand_rating = px.bar(
                top_rated_brands_plot, x="brand", y="avg_rating",
                title="Top Rated Brands (Average Score)",
                color="avg_rating", color_continuous_scale="Aggrnyl"
            )
            fig_brand_rating.update_layout(yaxis_range=[3.0, 5.0])
            st.plotly_chart(fig_brand_rating, use_container_width=True)
            
        col2_3, col2_4, col2_5 = st.columns([1, 1, 1])
        
        with col2_3:
            st.markdown("#### 🏆 Brand Dominance in Top 10 Ranks")
            # Count of products in top 10 positions per brand
            top_10_brands = df_brand[df_brand['position'] <= 10]['brand'].value_counts().head(10).reset_index()
            top_10_brands.columns = ['Brand', 'Top 10 Ranks Count']
            fig_top10 = px.bar(
                top_10_brands, x="Brand", y="Top 10 Ranks Count",
                title="Total Top 10 Position Appearances by Brand",
                color="Top 10 Ranks Count", color_continuous_scale="Purples"
            )
            st.plotly_chart(fig_top10, use_container_width=True)
            
        with col2_4:
            st.markdown("#### ⚡ Visibility Score by Brand")
            top_vis_brands_plot = brand_min_filter.sort_values(by='avg_vis', ascending=False).head(10)
            fig_brand_vis = px.bar(
                top_vis_brands_plot, x="brand", y="avg_vis",
                title="Average Visibility score per Brand",
                color="avg_vis", color_continuous_scale="solar"
            )
            st.plotly_chart(fig_brand_vis, use_container_width=True)
            
        with col2_5:
            st.markdown("#### 📈 Average Search Position (Rank) per Brand")
            top_pos_brands_plot = brand_min_filter.sort_values(by='avg_pos', ascending=True).head(10)
            fig_brand_pos = px.bar(
                top_pos_brands_plot, x="brand", y="avg_pos",
                title="Best Average Search Ranks (Lower is Better)",
                color="avg_pos", color_continuous_scale="Viridis_r"
            )
            st.plotly_chart(fig_brand_pos, use_container_width=True)

# ----------------------------------------------------
# TAB 3: PRICING INSIGHTS
# ----------------------------------------------------
with tabs[2]:
    st.subheader("Price Ranges, Outliers, and Discount Structures")
    
    # KPIs
    pkpi_col1, pkpi_col2, pkpi_col3, pkpi_col4 = st.columns(4)
    
    lowest_prod = df.loc[df['price'].idxmin()]
    highest_prod = df.loc[df['price'].idxmax()]
    discounted_pct = (df['discount_pct'] > 0).mean() * 100
    
    pkpi_col1.metric("Average Price", f"${avg_price:,.2f}")
    pkpi_col2.metric("Highest Priced Product", f"${highest_prod['price']:,.2f}", highest_prod['title'][:25] + "...")
    pkpi_col3.metric("Lowest Priced Product", f"${lowest_prod['price']:,.2f}", lowest_prod['title'][:25] + "...")
    pkpi_col4.metric("% Discounted Products", f"{discounted_pct:.1f}%")
    
    st.markdown("---")
    
    # Charts
    col3_1, col3_2 = st.columns(2)
    
    with col3_1:
        st.markdown("#### 📦 Product Volume by Price Range Tier")
        # Try qcut, if it fails due to duplicate edges (too many identical prices), use dynamic bin ranges
        try:
            df['price_tier'] = pd.qcut(
                df['price'], 
                q=4, 
                labels=['Budget', 'Lower Mid-Range', 'Upper Mid-Range', 'Premium']
            )
        except Exception:
            bins = [0, 50, 200, 1000, float('inf')]
            labels = ['Budget', 'Lower Mid-Range', 'Upper Mid-Range', 'Premium']
            df['price_tier'] = pd.cut(df['price'], bins=bins, labels=labels)
            
        tier_counts = df['price_tier'].value_counts().reindex(['Budget', 'Lower Mid-Range', 'Upper Mid-Range', 'Premium']).reset_index()
        tier_counts.columns = ['Price Tier', 'Products Count']
        fig_tier = px.bar(
            tier_counts, x="Price Tier", y="Products Count",
            title="Distribution of Catalog by Price Tier Category",
            color="Price Tier", color_discrete_sequence=px.colors.qualitative.Set2
        )
        st.plotly_chart(fig_tier, use_container_width=True)
        
    with col3_2:
        st.markdown("#### 💸 Price Distribution (Histogram with KDE Trend)")
        fig_price_kde = px.histogram(
            df, x="price", marginal="box", 
            title="Overall Price Density & Spread",
            color_discrete_sequence=["#E377C2"]
        )
        st.plotly_chart(fig_price_kde, use_container_width=True)
        
    col3_3, col3_4 = st.columns(2)
    
    with col3_3:
        st.markdown("#### 🎯 Price vs. Ranking Position")
        fig_price_rank = px.scatter(
            df, x="position", y="price",
            title="Do Higher Priced Items Ranks Higher on Search Lists?",
            color="platform", hover_data=["title", "brand"],
            labels={"position": "Search Position", "price": "Price ($)"}
        )
        st.plotly_chart(fig_price_rank, use_container_width=True)
        
    with col3_4:
        st.markdown("#### ⭐ Price vs. Rating Score")
        fig_price_rate = px.scatter(
            df, x="rating", y="price",
            title="Correlation Between Price & User Ratings",
            color="keyword", hover_data=["title", "brand"],
            labels={"rating": "Customer Rating", "price": "Price ($)"}
        )
        st.plotly_chart(fig_price_rate, use_container_width=True)
        
    col3_5, col3_6 = st.columns(2)
    
    with col3_5:
        st.markdown("#### 🏷️ Average Discount % by Brand (Top 15 Discounted)")
        brand_discounts = df[df['brand'].notna() & (df['brand'] != '')].groupby('brand')['discount_pct'].mean().reset_index()
        top_discount_brands = brand_discounts.sort_values(by='discount_pct', ascending=False).head(15)
        fig_discount_brand = px.bar(
            top_discount_brands, x="discount_pct", y="brand", orientation='h',
            title="Average Promo Percent Off by Brand",
            labels={"discount_pct": "Avg Discount (%)", "brand": "Brand"},
            color="discount_pct", color_continuous_scale="Oranges"
        )
        fig_discount_brand.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_discount_brand, use_container_width=True)
        
    with col3_6:
        st.markdown("#### 🏬 Average Discount % by Selling Platform")
        plat_discounts = df.groupby('platform')['discount_pct'].mean().reset_index()
        fig_discount_plat = px.bar(
            plat_discounts, x="platform", y="discount_pct",
            title="Aggressiveness of Promo Discounts across Selling Platforms",
            labels={"discount_pct": "Avg Discount (%)", "platform": "Platform"},
            color="discount_pct", color_continuous_scale="Reds"
        )
        st.plotly_chart(fig_discount_plat, use_container_width=True)

# ----------------------------------------------------
# TAB 4: PLATFORM COMPARISON
# ----------------------------------------------------
with tabs[3]:
    st.subheader("Platform Metrics and Inventory Share")
    
    # KPIs
    plkpi_col1, plkpi_col2, plkpi_col3, plkpi_col4 = st.columns(4)
    
    total_platforms = df['platform'].nunique()
    
    platform_agg = df.groupby('platform').agg(
        avg_rating=('rating', 'mean'),
        avg_price=('price', 'mean'),
        avg_pos=('position', 'mean'),
        count=('id', 'count')
    ).reset_index()
    
    best_plat = platform_agg.sort_values(by='avg_rating', ascending=False).iloc[0]
    cheapest_plat = platform_agg.sort_values(by='avg_price', ascending=True).iloc[0]
    largest_plat = platform_agg.sort_values(by='count', ascending=False).iloc[0]
    
    plkpi_col1.metric("Total Retail Channels", f"{total_platforms}")
    plkpi_col2.metric("Best Rated Platform", f"{best_plat['platform']}", f"{best_plat['avg_rating']:.2f} Rating")
    plkpi_col3.metric("Cheapest Platform", f"{cheapest_plat['platform']}", f"${cheapest_plat['avg_price']:,.2f} Avg")
    plkpi_col4.metric("Largest Platform (Catalog)", f"{largest_plat['platform']}", f"{largest_plat['count']} Listings")
    
    st.markdown("---")
    
    # Filter to top 15 platforms by count for visualizations to prevent cluttered axes
    top_plats_for_viz = platform_agg.sort_values(by='count', ascending=False).head(15)
    
    # Charts
    col4_1, col4_2 = st.columns(2)
    
    with col4_1:
        st.markdown("#### 📊 Inventory Volume per Platform (Top 15)")
        fig_plat_count = px.bar(
            top_plats_for_viz, x="platform", y="count",
            title="Product Count by Platform",
            color="count", color_continuous_scale="Greens",
            labels={"count": "Listings Count", "platform": "Platform"}
        )
        st.plotly_chart(fig_plat_count, use_container_width=True)
        
    with col4_2:
        st.markdown("#### 💵 Average Product Price by Platform (Top 15)")
        fig_plat_price = px.bar(
            top_plats_for_viz, x="platform", y="avg_price",
            title="Comparison of Average Selling Prices",
            color="avg_price", color_continuous_scale="Purples",
            labels={"avg_price": "Avg Price ($)", "platform": "Platform"}
        )
        st.plotly_chart(fig_plat_price, use_container_width=True)
        
    col4_3, col4_4 = st.columns(2)
    
    with col4_3:
        st.markdown("#### 🌟 Average Rating by Platform (Top 15)")
        fig_plat_rating_col = px.bar(
            top_plats_for_viz, x="platform", y="avg_rating",
            title="Platform Ratings Benchmark",
            color="avg_rating", color_continuous_scale="YlOrRd",
            labels={"avg_rating": "Avg Rating", "platform": "Platform"}
        )
        fig_plat_rating_col.update_layout(yaxis_range=[3.0, 5.0])
        st.plotly_chart(fig_plat_rating_col, use_container_width=True)
        
    with col4_4:
        st.markdown("#### 🔍 Average Search Rank Position by Platform (Top 15)")
        fig_plat_pos = px.bar(
            top_plats_for_viz, x="platform", y="avg_pos",
            title="Average Search Listing Rank per Platform (Lower is Better)",
            color="avg_pos", color_continuous_scale="Icefire",
            labels={"avg_pos": "Avg Rank Position", "platform": "Platform"}
        )
        st.plotly_chart(fig_plat_pos, use_container_width=True)
        
    st.markdown("#### 🏢 Brand Distribution across Selling Platforms (Top 10 Platforms & Brands)")
    top_10_brands_list = df['brand'].value_counts().head(10).index
    top_10_platforms_list = df['platform'].value_counts().head(10).index
    df_top_brands_plat = df[df['brand'].isin(top_10_brands_list) & df['platform'].isin(top_10_platforms_list)]
    
    brand_plat_share = df_top_brands_plat.groupby(['platform', 'brand']).size().reset_index(name='count')
    fig_stacked = px.bar(
        brand_plat_share, x="platform", y="count", color="brand",
        title="Presence of Top 10 Major Brands in Top 10 Storefronts",
        labels={"count": "Products Count", "platform": "Platform", "brand": "Brand"},
        color_discrete_sequence=px.colors.qualitative.D3
    )
    st.plotly_chart(fig_stacked, use_container_width=True)

# ----------------------------------------------------
# TAB 5: VISIBILITY & RANKING
# ----------------------------------------------------
with tabs[4]:
    st.subheader("Listing Rankings & Geometric Decay Analysis")
    
    # KPIs
    vkpi_col1, vkpi_col2, vkpi_col3, vkpi_col4 = st.columns(4)
    
    avg_pos = df['position'].mean()
    rank1_count = (df['position'] == 1).sum()
    top_10_share = (df['position'] <= 10).mean() * 100
    
    vkpi_col1.metric("Average Rank Position", f"#{avg_pos:.1f}")
    vkpi_col2.metric("Keyword #1 Ranks Count", f"{rank1_count} products")
    vkpi_col3.metric("Avg Visibility Score", f"{avg_visibility:.2f} pts")
    vkpi_col4.metric("Share in Top 10 Positions", f"{top_10_share:.1f}%")
    
    st.markdown("---")
    
    # Charts
    col5_1, col5_2 = st.columns(2)
    
    with col5_1:
        st.markdown("#### 📊 Search Rankings Distribution")
        fig_rank_hist = px.histogram(
            df, x="position", nbins=50,
            title="Distribution of Catalog items across Page Position Ranks",
            labels={"position": "Search Position (Rank)"},
            color_discrete_sequence=["#2CA02C"]
        )
        st.plotly_chart(fig_rank_hist, use_container_width=True)
        
    with col5_2:
        st.markdown("#### 🌟 Ratings vs. Search Position (Rank)")
        fig_rank_rate = px.scatter(
            df, x="position", y="rating",
            title="Does Listing Position Correlate with Higher Ratings?",
            color="platform", hover_data=["title", "brand"],
            labels={"position": "Search Position", "rating": "Rating"}
        )
        st.plotly_chart(fig_rank_rate, use_container_width=True)
        
    col5_3, col5_4 = st.columns(2)
    
    with col5_3:
        st.markdown("#### 💬 Reviews Engagement vs. Search Ranking")
        # Keep reviews > 0 to have clean bubble charts
        df_rev = df[df['reviews'] > 0]
        fig_rank_bubble = px.scatter(
            df_rev, x="position", y="price", size="reviews", color="platform",
            title="Review Count Volume by Ranking & Price (Bubble Size = Reviews Count)",
            hover_data=["title", "brand"], size_max=50,
            labels={"position": "Search Position (Rank)", "price": "Price ($)"}
        )
        st.plotly_chart(fig_rank_bubble, use_container_width=True)
        
    with col5_4:
        st.markdown("#### ⚡ Visibility Score by Brand (Top 15)")
        brand_vis_agg = df_brand.groupby('brand')['visibility_score'].mean().reset_index()
        top_vis_brands = brand_vis_agg.sort_values(by='visibility_score', ascending=False).head(15)
        fig_brand_vis_bar = px.bar(
            top_vis_brands, x="visibility_score", y="brand", orientation='h',
            title="Average Visibility score per Brand",
            labels={"visibility_score": "Avg Visibility Score (pts)", "brand": "Brand"},
            color="visibility_score", color_continuous_scale="Viridis"
        )
        fig_brand_vis_bar.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_brand_vis_bar, use_container_width=True)

# ----------------------------------------------------
# TAB 6: PRODUCT EXPLORER
# ----------------------------------------------------
with tabs[5]:
    st.subheader("Granular Catalog Explorer and Product Lookup")
    
    # Keyword title search
    search_query = st.text_input("🔍 Search product title keyword (e.g. 'iPhone 15', 'HP Laptop'):", value="")
    
    # Apply search filter
    if search_query:
        explorer_df = df[df['title'].str.contains(search_query, case=False, na=False)]
    else:
        explorer_df = df
        
    # KPIs for the filtered subset
    ekpi_col1, ekpi_col2, ekpi_col3 = st.columns(3)
    
    sub_count = len(explorer_df)
    sub_price = explorer_df['price'].mean() if sub_count > 0 else 0.0
    sub_rating = explorer_df['rating'].mean() if sub_count > 0 else 0.0
    
    ekpi_col1.metric("Filtered Product Volume", f"{sub_count:,}")
    ekpi_col2.metric("Filtered Average Price", f"${sub_price:,.2f}")
    ekpi_col3.metric("Filtered Average Rating", f"{sub_rating:.2f} / 5.0")
    
    st.markdown("---")
    
    # Sortable product table
    if not explorer_df.empty:
        # Prepare displaying dataset
        display_cols = [
            'id', 'title', 'brand', 'price', 'rating', 
            'reviews', 'platform', 'position', 'discount_pct'
        ]
        display_df = explorer_df[display_cols].copy()
        display_df.rename(columns={
            'id': 'ID',
            'title': 'Product Title',
            'brand': 'Brand',
            'price': 'Price ($)',
            'rating': 'Rating',
            'reviews': 'Reviews Count',
            'platform': 'Platform',
            'position': 'Search Position',
            'discount_pct': 'Discount (%)'
        }, inplace=True)
        
        st.markdown("💡 *Click on column headers to sort the table. Select a row to see detail cards.*")
        
        # Interactive Selection Table
        event = st.dataframe(
            display_df,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            use_container_width=True
        )
        
        # Selection Drill-through Detail
        selected_rows = event.get("selection", {}).get("rows", [])
        if selected_rows:
            idx = selected_rows[0]
            prod_row = display_df.iloc[idx]
            
            # Fetch full product record from original df
            full_prod = df[df['id'] == int(prod_row['ID'])].iloc[0]
            
            st.markdown(f"### 🔍 Detailed Product Deep-Dive (ID: {full_prod['id']})")
            
            detail_col1, detail_col2 = st.columns(2)
            with detail_col1:
                st.markdown(f"""
                <div class="card">
                    <h3>{full_prod['title']}</h3>
                    <p><b>Brand:</b> {full_prod['brand']}</p>
                    <p><b>Category Keyword:</b> {full_prod['keyword']}</p>
                    <p><b>Retail Channel (Platform):</b> {full_prod['platform']}</p>
                    <p><b>Delivery Policy:</b> {full_prod['delivery']}</p>
                </div>
                """, unsafe_allow_html=True)
                
            with detail_col2:
                st.markdown(f"""
                <div class="card" style="border-left-color: #2CA02C;">
                    <h3>Performance & Pricing</h3>
                    <p><b>Selling Price:</b> ${full_prod['price']:,.2f} (Original old price: ${full_prod['old_price']:,.2f})</p>
                    <p><b>Saving Discount:</b> {full_prod['discount_pct']:.1f}% (${full_prod['discount']:,.2f} off)</p>
                    <p><b>Customer Score:</b> {full_prod['rating']:.1f} stars ({full_prod['reviews']:,} reviews)</p>
                    <p><b>Search Index Rank:</b> Position #{int(full_prod['position'])}</p>
                    <p><b>Calculated Visibility Score:</b> {full_prod['visibility_score']:.2f} points</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("👆 Click any row check-box in the table above to drill-down and see all details for that specific item.")
            
        st.markdown("---")
        
        # Explorer sub-charts
        col6_1, col6_2 = st.columns(2)
        
        with col6_1:
            st.markdown("#### 🌟 Product Rating vs. Pricing Scatter")
            fig_rate_price = px.scatter(
                explorer_df, x="price", y="rating", color="brand",
                size="reviews", hover_data=["title", "platform"],
                title="Filtered Products Rating vs Price Scatter",
                labels={"price": "Price ($)", "rating": "Rating"}
            )
            st.plotly_chart(fig_rate_price, use_container_width=True)
            
        with col6_2:
            st.markdown("#### 💬 Reviews Engagement vs. Search position")
            fig_rev_rank = px.scatter(
                explorer_df[explorer_df['reviews'] > 0], x="position", y="price", size="reviews", color="platform",
                title="Reviews volume by Ranking and Price (Filtered)",
                hover_data=["title", "brand"], size_max=50,
                labels={"position": "Search Position (Rank)", "price": "Price ($)"}
            )
            st.plotly_chart(fig_rev_rank, use_container_width=True)
            
    else:
        st.info("No products match the search phrase.")
