import os
import ssl
import streamlit as st
import pandas as pd
import xmlrpc.client
import plotly.express as px
from dotenv import load_dotenv

# Xử lý chứng chỉ SSL trên macOS
ssl._create_default_https_context = ssl._create_unverified_context

st.set_page_config(page_title="ERP Kỹ Thuật HCM - Siêu Tốc", page_icon="⚡", layout="wide")

# ================= ⚡ CHƯƠNG TRÌNH CHÍNH DASHBOARD =================
st.markdown("""
    <style>
    /* Chỉ cố định 320px khi Sidebar đang MỞ */
    [data-testid="stSidebar"][aria-expanded="true"] { min-width: 320px !important; }
    div[data-testid="stCheckbox"] { margin-bottom: -10px !important; }
    </style>
""", unsafe_allow_html=True)

load_dotenv()

# Ưu tiên lấy từ Secrets trên Streamlit Cloud, nếu không có mới lấy từ .env
URL = st.secrets.get("ERP_URL", os.getenv("ERP_URL", ""))
DB = st.secrets.get("ERP_DB", os.getenv("ERP_DB", ""))
USER = st.secrets.get("ERP_USER", os.getenv("ERP_USER", ""))
PASSWORD = st.secrets.get("ERP_PASSWORD", os.getenv("ERP_PASSWORD", ""))

DANH_SACH_KT_HCM = [
    'Kỹ thuật - Anh Tài',
    'Kỹ thuật - Gia Bảo',
    'Kỹ thuật - Gia Thạnh',
    'Kỹ thuật - Huỳnh Văn Nhật',
    'Kỹ thuật - Nguyên Huy',
    'Kỹ thuật - Trần Nhật Phú',
    'Kỹ thuật - Viết Dương',
    'Kỹ thuật - Võ Xuân Tùng'
]

st.title("⚡ DASHBOARD TỨ TRỤ: KỸ THUẬT HCM")

@st.cache_data(ttl=300)  # Giảm cache xuống 5 phút để dữ liệu cập nhật nhanh hơn
def load_all_data():
    try:
        clean_url = URL.strip('/')
        common = xmlrpc.client.ServerProxy(f"{clean_url}/xmlrpc/2/common")
        uid = common.authenticate(DB, USER, PASSWORD, {})
        if not uid: return None, "Xác thực Odoo thất bại!"
        models = xmlrpc.client.ServerProxy(f"{clean_url}/xmlrpc/2/object")
        
        # 1. Trích xuất DVTC
        fields_dvtc = ['create_date', 'x_studio_nguoi_thuc_hien', 'x_studio_san_pham', 'x_studio_so_luong', 'x_thanh_tien', 'x_studio_point']
        records_dvtc = models.execute_kw(DB, uid, PASSWORD, 'x_dich_vu_ky_thuat_line', 'search_read', [[]], {'fields': fields_dvtc, 'limit': 3000, 'order': 'create_date desc'})
        
        # 2. Trích xuất DVTP (POS) - Đồng bộ lọc các đơn đã thanh toán/hoàn tất giống ERP
        fields_pos = ['date_order', 'user_id', 'name', 'amount_total', 'state']
        domain_pos = [['state', 'in', ['paid', 'done', 'invoiced']]]
        records_pos = models.execute_kw(DB, uid, PASSWORD, 'pos.order', 'search_read', [domain_pos], {'fields': fields_pos, 'limit': 3000, 'order': 'date_order desc'})

        # 3. Trích xuất Ticket (Hỗ trợ kỹ thuật & Giao hàng)
        fields_ticket = ['create_date', 'user_id', 'name', 'stage_id', 'team_id']
        records_ticket = models.execute_kw(DB, uid, PASSWORD, 'helpdesk.ticket', 'search_read', [[]], {'fields': fields_ticket, 'limit': 3000, 'order': 'create_date desc'})
        
        return (records_dvtc, records_pos, records_ticket), None
    except Exception as e:
        return None, str(e)

with st.spinner("Đang trích xuất dữ liệu ERP..."):
    data, error = load_all_data()

if error:
    st.error(error)
elif data:
    records_dvtc, records_pos, records_ticket = data
    
    # Xử lý DVTC
    df_dvtc = pd.DataFrame(records_dvtc)
    if not df_dvtc.empty:
        df_dvtc['Thời gian'] = pd.to_datetime(df_dvtc['create_date']) + pd.Timedelta(hours=7)
        df_dvtc['Nhân viên'] = df_dvtc['x_studio_nguoi_thuc_hien'].apply(lambda x: x[1] if isinstance(x, list) else str(x or ''))
        df_dvtc['Dịch vụ'] = df_dvtc['x_studio_san_pham'].apply(lambda x: x[1] if isinstance(x, list) else str(x or ''))
        df_dvtc['Số lượng'] = df_dvtc['x_studio_so_luong'].fillna(1)
        df_dvtc['Điểm kỹ thuật'] = df_dvtc['x_studio_point'].fillna(0.0)
        df_dvtc['Thành tiền'] = 0.0
        df_dvtc['Nhóm dịch vụ'] = 'DVTC (Tiêu chuẩn)'
    
    # Xử lý POS / DVTP
    df_pos = pd.DataFrame(records_pos)
    if not df_pos.empty:
        df_pos['Thời gian'] = pd.to_datetime(df_pos['date_order']) + pd.Timedelta(hours=7)
        df_pos['Nhân viên'] = df_pos['user_id'].apply(lambda x: x[1] if isinstance(x, list) else str(x or ''))
        df_pos['Dịch vụ'] = df_pos['name'].apply(lambda x: f"Đơn POS: {x}")
        df_pos['Số lượng'] = 1
        df_pos['Điểm kỹ thuật'] = 0.0
        df_pos['Thành tiền'] = df_pos['amount_total'].fillna(0.0)
        df_pos['Nhóm dịch vụ'] = 'DVTP (Thu phí)'

    cols = ['Thời gian', 'Nhân viên', 'Nhóm dịch vụ', 'Dịch vụ', 'Số lượng', 'Điểm kỹ thuật', 'Thành tiền']
    df_list = []
    if not df_dvtc.empty: df_list.append(df_dvtc[cols])
    if not df_pos.empty: df_list.append(df_pos[cols])
    
    if df_list:
        df = pd.concat(df_list, ignore_index=True)
        df = df[df['Nhân viên'].isin(DANH_SACH_KT_HCM)]
        df = df.sort_values(by='Thời gian', ascending=False)
    else:
        df = pd.DataFrame(columns=cols)

    # Xử lý Tickets
    df_ticket_all = pd.DataFrame(records_ticket)
    df_htkt = pd.DataFrame()
    df_giao_hang = pd.DataFrame()

    if not df_ticket_all.empty:
        df_ticket_all['Thời gian'] = pd.to_datetime(df_ticket_all['create_date']) + pd.Timedelta(hours=7)
        df_ticket_all['Nhân viên'] = df_ticket_all['user_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Chưa phân công')
        df_ticket_all['Giai đoạn'] = df_ticket_all['stage_id'].apply(lambda x: x[1] if isinstance(x, list) else str(x or ''))
        df_ticket_all['Đội'] = df_ticket_all['team_id'].apply(lambda x: x[1] if isinstance(x, list) else '')

        df_htkt = df_ticket_all[df_ticket_all['Đội'].str.contains('Hỗ trợ|Kỹ thuật', case=False, na=False)].copy()
        if not df_htkt.empty:
            df_htkt['Trạng thái hỗ trợ'] = df_htkt['Giai đoạn'].apply(
                lambda s: 'Đã hoàn thành' if any(kw in str(s).lower() for kw in ['hoàn thành', 'đóng', 'done', 'closed', 'thành công']) else ('Đã hủy' if any(kw in str(s).lower() for kw in ['hủy', 'huy', 'cancel']) else 'Đang chờ xử lý')
            )
            df_htkt = df_htkt[df_htkt['Nhân viên'].isin(DANH_SACH_KT_HCM) | (df_htkt['Nhân viên'] == 'Chưa phân công')]

        df_giao_hang = df_ticket_all[df_ticket_all['Đội'].str.contains('Giao hàng', case=False, na=False)].copy()
        if not df_giao_hang.empty:
            def build_delivery_status(row):
                nv = str(row.get('Nhân viên', '')).strip()
                if nv == 'Chưa phân công' or not nv or nv.lower() == 'nan':
                    return '⚪ Chưa phân công'
                stage = str(row.get('Giai đoạn', '')).strip().lower()
                if any(kw in stage for kw in ['hủy', 'huỷ', 'huy', 'cancel']):
                    return '🔴 Hủy / Bất thành'
                if any(kw in stage for kw in ['thành công', 'hoàn thành', 'done', 'success']):
                    return '🟢 Thành công'
                return '🟡 Đang xử lý'
            
            df_giao_hang['Trạng thái giao hàng'] = df_giao_hang.apply(build_delivery_status, axis=1)

    # SIDEBAR
    st.sidebar.header("🔍 Cấu hình Bộ lọc HCM")
    nhom_dv_list = ["Tất cả"] + sorted(df['Nhóm dịch vụ'].unique().tolist()) if not df.empty else ["Tất cả"]
    selected_nhom = st.sidebar.selectbox("Phân loại Dịch vụ:", nhom_dv_list)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Nhân Viên Kỹ Thuật:**")
    all_checked = st.sidebar.checkbox("Chọn tất cả", value=True)
    selected_nvs = []
    for nv in sorted(DANH_SACH_KT_HCM):
        display_name = nv.replace('Kỹ thuật - ', 'KT – ')
        if st.sidebar.checkbox(display_name, value=all_checked, key=f"cb_{nv}"):
            selected_nvs.append(nv)

    st.sidebar.markdown("---")
    
    # Ép múi giờ chuẩn Việt Nam (UTC+7)
    now_vn = pd.Timestamp.now(tz='UTC') + pd.Timedelta(hours=7)
    today_vn = now_vn.date()
    default_start = today_vn.replace(day=1)

    # Bộ chọn ngày mở tự do
    date_range = st.sidebar.date_input(
        "Khoảng thời gian:", 
        value=(default_start, today_vn)
    )

    # Lọc theo Nhân viên & Nhóm dịch vụ
    df_filtered = df[df['Nhân viên'].isin(selected_nvs)] if selected_nvs and not df.empty else pd.DataFrame(columns=df.columns)
    if selected_nhom != "Tất cả" and not df_filtered.empty: 
        df_filtered = df_filtered[df_filtered['Nhóm dịch vụ'] == selected_nhom]

    # Lọc theo Khoảng thời gian
    if len(date_range) == 2 and not df_filtered.empty:
        df_filtered = df_filtered[(df_filtered['Thời gian'].dt.date >= date_range[0]) & (df_filtered['Thời gian'].dt.date <= date_range[1])]

    df_htkt_filtered = df_htkt[df_htkt['Nhân viên'].isin(selected_nvs + ['Chưa phân công'])] if not df_htkt.empty and selected_nvs else pd.DataFrame()
    if len(date_range) == 2 and not df_htkt_filtered.empty:
        df_htkt_filtered = df_htkt_filtered[(df_htkt_filtered['Thời gian'].dt.date >= date_range[0]) & (df_htkt_filtered['Thời gian'].dt.date <= date_range[1])]

    df_gh_filtered = df_giao_hang[df_giao_hang['Nhân viên'].isin(selected_nvs + ['Chưa phân công'])] if not df_giao_hang.empty and selected_nvs else pd.DataFrame()
    if len(date_range) == 2 and not df_gh_filtered.empty:
        df_gh_filtered = df_gh_filtered[(df_gh_filtered['Thời gian'].dt.date >= date_range[0]) & (df_gh_filtered['Thời gian'].dt.date <= date_range[1])]

    if st.sidebar.button("🔄 Cập nhật hệ thống", type="primary"):
        st.cache_data.clear()
        st.rerun()

    # METRICS
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("1. Điểm DVTC", round(df_filtered['Điểm kỹ thuật'].sum(), 2) if not df_filtered.empty else 0)
    col2.metric("2. Doanh thu DVTP", f"{df_filtered['Thành tiền'].sum():,.0f} VNĐ" if not df_filtered.empty else "0 VNĐ")
    htkt_pending = len(df_htkt_filtered[df_htkt_filtered['Trạng thái hỗ trợ'] == 'Đang chờ xử lý']) if not df_htkt_filtered.empty else 0
    col3.metric("3. Vé Hỗ Trợ Đang Chờ 🔴", htkt_pending)
    gh_pending = len(df_gh_filtered[df_gh_filtered['Trạng thái giao hàng'] == '🟡 Đang xử lý']) if not df_gh_filtered.empty else 0
    gh_unassigned = len(df_gh_filtered[df_gh_filtered['Trạng thái giao hàng'] == '⚪ Chưa phân công']) if not df_gh_filtered.empty else 0
    col4.metric("4. Đơn Giao Đang Chờ 🟡", gh_pending, delta=f"{gh_unassigned} chưa gán", delta_color="inverse")

    st.markdown("---")

    # BIỂU ĐỒ & BẢNG
    st.subheader("📊 Trụ 1 & 2: Xếp hạng & Chi tiết DVTC - DVTP")
    if not df_filtered.empty:
        c1, c2 = st.columns(2)
        if selected_nhom in ["Tất cả", "DVTC (Tiêu chuẩn)"]:
            with c1 if selected_nhom == "Tất cả" else st.container():
                dvtc_chart = df_filtered[df_filtered['Nhóm dịch vụ'] == 'DVTC (Tiêu chuẩn)'].groupby('Nhân viên')['Điểm kỹ thuật'].sum().reset_index().sort_values(by='Điểm kỹ thuật', ascending=True)
                if not dvtc_chart.empty:
                    fig_point = px.bar(dvtc_chart, y='Nhân viên', x='Điểm kỹ thuật', orientation='h', title='🏆 Điểm Kỹ Thuật (DVTC)', color_discrete_sequence=['#00CC96'])
                    fig_point.update_layout(height=300)
                    st.plotly_chart(fig_point, use_container_width=True)
                st.dataframe(df_filtered[df_filtered['Nhóm dịch vụ'] == 'DVTC (Tiêu chuẩn)'][['Thời gian', 'Nhân viên', 'Dịch vụ', 'Số lượng', 'Điểm kỹ thuật']], width='stretch')

        if selected_nhom in ["Tất cả", "DVTP (Thu phí)"]:
            with c2 if selected_nhom == "Tất cả" else st.container():
                dvtp_chart = df_filtered[df_filtered['Nhóm dịch vụ'] == 'DVTP (Thu phí)'].groupby('Nhân viên')['Thành tiền'].sum().reset_index().sort_values(by='Thành tiền', ascending=True)
                if not dvtp_chart.empty:
                    fig_rev = px.bar(dvtp_chart, y='Nhân viên', x='Thành tiền', orientation='h', title='💰 Doanh Thu (DVTP)', color_discrete_sequence=['#EF553B'])
                    fig_rev.update_layout(height=300)
                    st.plotly_chart(fig_rev, use_container_width=True)
                st.dataframe(df_filtered[df_filtered['Nhóm dịch vụ'] == 'DVTP (Thu phí)'][['Thời gian', 'Nhân viên', 'Dịch vụ', 'Thành tiền']].style.format({'Thành tiền': '{:,.0f} VNĐ'}), width='stretch')

    st.markdown("---")
    st.subheader("🛠️ Trụ 3: Quản Lý Vé Hỗ Trợ Chưa Xử Lý")
    if not df_htkt_filtered.empty:
        df_htkt_pending = df_htkt_filtered[df_htkt_filtered['Trạng thái hỗ trợ'] == 'Đang chờ xử lý']
        if not df_htkt_pending.empty:
            htkt_chart_data = df_htkt_pending.groupby(['Nhân viên', 'Giai đoạn']).size().reset_index(name='Số lượng vé đọng')
            fig_htkt = px.bar(htkt_chart_data, y='Nhân viên', x='Số lượng vé đọng', color='Giai đoạn', orientation='h', title='Vé Đang Chờ Phân Theo Nhân Viên', color_discrete_sequence=px.colors.qualitative.Set2)
            fig_htkt.update_layout(height=320, barmode='stack')
            st.plotly_chart(fig_htkt, use_container_width=True)
            st.dataframe(df_htkt_pending[['Thời gian', 'name', 'Nhân viên', 'Giai đoạn']].rename(columns={'name': 'Tiêu đề vé'}), width='stretch')

    st.markdown("---")
    st.subheader("🚚 Trụ 4: Quản Lý Tiến Độ Đội Giao Hàng")
    if not df_gh_filtered.empty:
        gh_chart_data = df_gh_filtered.groupby(['Nhân viên', 'Trạng thái giao hàng']).size().reset_index(name='Số đơn')
        fig_gh = px.bar(gh_chart_data, y='Nhân viên', x='Số đơn', color='Trạng thái giao hàng', orientation='h', title='Thống kê Đơn Giao Hàng', color_discrete_map={'⚪ Chưa phân công': '#7F7F7F', '🔴 Hủy / Bất thành': '#E74C3C', '🟡 Đang xử lý': '#FF7F0E', '🟢 Thành công': '#2CA02C'})
        fig_gh.update_layout(height=380, barmode='stack')
        st.plotly_chart(fig_gh, use_container_width=True)
        st.dataframe(df_gh_filtered[['Thời gian', 'name', 'Nhân viên', 'Trạng thái giao hàng', 'Giai đoạn']].rename(columns={'name': 'Mã đơn'}), width='stretch')
