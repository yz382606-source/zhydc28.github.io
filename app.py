import requests
import ta
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging
import time
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# 设置页面配置
st.set_page_config(
   page_title="鹅的DC28×MA 金叉死叉扫描器",
   page_icon="📈",
   layout="wide",
   initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
   /* 主要背景和主题 */
   .main {
       background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
       padding-top: 2rem;
       color: #f0f2f6;
   }
   
   /* 标题样式 */
   .big-title {
       font-size: 3rem;
       font-weight: 700;
       background: linear-gradient(90deg, #00d2ff, #3a7bd5);
       -webkit-background-clip: text;
       -webkit-text-fill-color: transparent;
       text-align: center;
       margin-bottom: 1rem;
       text-shadow: 0 2px 4px rgba(0,0,0,0.2);
   }
   
   .subtitle {
       text-align: center;
       color: #a0aec0;
       font-size: 1.2rem;
       margin-bottom: 2rem;
   }
   
   /* 卡片样式 */
   .metric-card {
       background: linear-gradient(135deg, #1a2a6c, #b21f1f, #1a2a6c);
       padding: 1.5rem;
       border-radius: 15px;
       color: white;
       text-align: center;
       margin: 0.5rem 0;
       box-shadow: 0 6px 12px rgba(0,0,0,0.15);
       transition: all 0.3s ease;
       border: 1px solid rgba(255,255,255,0.1);
   }
   
   .metric-card:hover {
       transform: translateY(-5px);
       box-shadow: 0 12px 24px rgba(0,0,0,0.2);
   }
   
   .stat-card {
       background: rgba(30, 41, 59, 0.8);
       padding: 1.5rem;
       border-radius: 15px;
       box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
       border-left: 4px solid #3a7bd5;
       margin: 1rem 0;
       color: #e2e8f0;
   }
   
   /* 按钮样式 */
   .stButton > button {
       width: 100%;
       background: linear-gradient(90deg, #00d2ff, #3a7bd5);
       color: white;
       border: none;
       padding: 1rem 2rem;
       border-radius: 30px;
       font-size: 1.1rem;
       font-weight: 600;
       transition: all 0.3s ease;
       box-shadow: 0 4px 6px rgba(0,0,0,0.1);
   }
   
   .stButton > button:hover {
       transform: translateY(-3px);
       box-shadow: 0 8px 15px rgba(0,0,0,0.2);
       background: linear-gradient(90deg, #00c6ff, #0072ff);
   }
   
   /* 数据表格样式 */
   .dataframe {
       border-radius: 15px;
       overflow: hidden;
       background: rgba(30, 41, 59, 0.8);
       color: #e2e8f0;
   }
   
   table.dataframe th {
       background: #1a2a6c !important;
       color: white !important;
   }
   
   /* 侧边栏样式 */
   [data-testid="stSidebar"] {
       background: linear-gradient(180deg, #0f2027, #203a43) !important;
       border-right: 1px solid rgba(255,255,255,0.1);
   }
   
   /* 警告和信息框样式 */
   .stAlert {
       border-radius: 15px;
       background: rgba(30, 41, 59, 0.8);
   }
   
   /* 进度条样式 */
   .stProgress > div > div {
       background: linear-gradient(90deg, #00d2ff, #3a7bd5);
       border-radius: 10px;
   }
   
   /* 分隔线 */
   .stMarkdown hr {
       border: 1px solid rgba(255,255,255,0.1);
       margin: 2rem 0;
   }
   
   /* 图表容器 */
   .plot-container {
       background: rgba(30, 41, 59, 0.8);
       border-radius: 15px;
       padding: 1.5rem;
       box-shadow: 0 4px 6px rgba(0,0,0,0.1);
   }
</style>
""", unsafe_allow_html=True)

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置常量
class Config:
   ENDPOINTS = ["https://api.bitget.com"]
   PRODUCT_TYPE = "usdt-futures"
   LIMIT = 400  # 增加K线数量以支持MA350
   DC_PERIOD = 28
   SLEEP_BETWEEN_REQUESTS = 0.5
   MAX_WORKERS = 10
   
   # UI配置
   TIMEFRAMES = {
       "15分钟": "15m",
       "30分钟": "30m", 
       "1小时": "1H",
       "4小时": "4H", 
       "1天": "1D"
   }
   
   # MA周期选项
   MA_OPTIONS = [20, 70, 150, 200, 350]

def create_header():
   """创建页面头部"""
   st.markdown('<h1 class="big-title">📈 鹅的DC28×MA 金叉死叉扫描器</h1>', unsafe_allow_html=True)
   st.markdown('<p class="subtitle">🚀 DC28通道中轨与MA均线交叉信号扫描 - 捕捉趋势转折点</p>', unsafe_allow_html=True)
   
   # 添加分隔线
   st.markdown("---")

def create_sidebar():
   """创建侧边栏"""
   with st.sidebar:
       st.markdown("### ⚙️ 扫描设置")
       
       # 时间框架选择
       timeframe_display = st.selectbox(
           "📊 时间框架",
           options=list(Config.TIMEFRAMES.keys()),
           index=2,  # 默认1小时
           help="选择K线时间周期"
       )
       timeframe = Config.TIMEFRAMES[timeframe_display]
       
       # MA周期选择
       ma_period = st.selectbox(
           "📈 MA均线周期",
           options=Config.MA_OPTIONS,
           index=3,  # 默认200
           help="选择移动平均线周期"
       )
       
       st.markdown("### 🎯 交叉信号设置")
       
       # 信号类型选择
       signal_types = st.multiselect(
           "选择扫描信号",
           options=["金叉信号", "死叉信号"],
           default=["金叉信号", "死叉信号"],
           help=f"金叉：DC28中轨上穿MA{ma_period}做多；死叉：DC28中轨下穿MA{ma_period}做空"
       )
       
       # 交叉确认周期
       cross_confirm_bars = st.slider(
           "交叉确认周期",
           min_value=1,
           max_value=5,
           value=2,
           help="最近N根K线内发生的交叉才显示"
       )
       
       # 高级设置
       with st.expander("🔧 高级设置"):
           show_charts = st.checkbox("显示图表分析", value=True)
           min_volume = st.number_input("最小成交量过滤", value=500000.0, help="过滤低成交量币种")
           price_position_strict = st.checkbox("严格价格位置验证", value=True, help="严格验证K线价格位置")
           
       return timeframe, ma_period, signal_types, cross_confirm_bars, show_charts, min_volume, price_position_strict

def ping_endpoint(endpoint: str) -> bool:
   """测试端点是否可用"""
   url = f"{endpoint}/api/v2/mix/market/candles"
   params = {
       "symbol": "BTCUSDT",
       "granularity": "4H",
       "limit": 1,
       "productType": Config.PRODUCT_TYPE,
   }
   try:
       r = requests.get(url, params=params, timeout=5)
       return r.status_code == 200 and r.json().get("code") == "00000"
   except:
       return False

def get_working_endpoint() -> str:
   """获取可用端点"""
   for ep in Config.ENDPOINTS:
       for _ in range(3):
           if ping_endpoint(ep):
               return ep
           time.sleep(1)
   raise RuntimeError("无可用端点，请检查网络连接")

def get_usdt_symbols(base: str) -> List[str]:
   """获取USDT永续合约交易对"""
   url = f"{base}/api/v2/mix/market/contracts"
   params = {"productType": Config.PRODUCT_TYPE}
   
   try:
       r = requests.get(url, params=params, timeout=5)
       j = r.json()
       if j.get("code") != "00000":
           raise RuntimeError(f"获取交易对失败: {j}")
       symbols = [c["symbol"] for c in j["data"]]
       logger.info(f"找到 {len(symbols)} 个USDT永续合约")
       return symbols
   except Exception as e:
       logger.error(f"获取交易对错误: {e}")
       raise

def fetch_candles(base: str, symbol: str, granularity: str) -> pd.DataFrame:
   """获取K线数据"""
   url = f"{base}/api/v2/mix/market/candles"
   params = {
       "symbol": symbol,
       "granularity": granularity,
       "limit": Config.LIMIT,
       "productType": Config.PRODUCT_TYPE,
   }
   
   try:
       r = requests.get(url, params=params, timeout=10)
       j = r.json()
       if j.get("code") != "00000":
           return pd.DataFrame()
           
       cols = ["ts", "open", "high", "low", "close", "volume_base", "volume_quote"]
       df = pd.DataFrame(j["data"], columns=cols)
       df[["open", "high", "low", "close", "volume_base", "volume_quote"]] = df[
           ["open", "high", "low", "close", "volume_base", "volume_quote"]
       ].astype(float)
       df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms")
       return df.sort_values("ts").reset_index(drop=True)
   except Exception as e:
       logger.error(f"{symbol} K线获取失败: {e}")
       return pd.DataFrame()

def fetch_all_tickers(base: str) -> Dict[str, dict]:
   """批量获取ticker数据"""
   url = f"{base}/api/v2/mix/market/tickers"
   params = {"productType": Config.PRODUCT_TYPE}
   
   try:
       r = requests.get(url, params=params, timeout=5)
       j = r.json()
       
       logger.info(f"Ticker API响应: code={j.get('code')}, msg={j.get('msg')}")
       
       if j.get("code") != "00000":
           logger.error(f"API返回错误: {j}")
           return {}
           
       if not isinstance(j.get("data"), list):
           logger.error(f"API数据格式错误: {type(j.get('data'))}")
           return {}
       
       tickers = {}
       for item in j["data"]:
           try:
               if len(tickers) == 0:
                   logger.info(f"Ticker数据结构示例: {list(item.keys())}")
               
               symbol = item.get("symbol", "")
               if not symbol:
                   continue
               
               # 兼容不同的字段名
               change24h = 0.0
               if "change24h" in item:
                   change24h = float(item["change24h"]) * 100
               elif "chgUtc" in item:
                   change24h = float(item["chgUtc"]) * 100
               elif "changeUtc24h" in item:
                   change24h = float(item["changeUtc24h"]) * 100
               
               # 成交量字段
               volume = 0.0
               if "baseVolume" in item:
                   volume = float(item["baseVolume"])
               elif "baseVol" in item:
                   volume = float(item["baseVol"])
               elif "vol24h" in item:
                   volume = float(item["vol24h"])
               
               # 价格字段
               price = 0.0
               if "close" in item:
                   price = float(item["close"])
               elif "last" in item:
                   price = float(item["last"])
               elif "lastPr" in item:
                   price = float(item["lastPr"])
               
               tickers[symbol] = {
                   "change24h": change24h,
                   "volume": volume,
                   "price": price
               }
               
           except (ValueError, KeyError, TypeError) as e:
               logger.warning(f"处理ticker数据失败 {item.get('symbol', 'unknown')}: {e}")
               continue
       
       logger.info(f"成功获取 {len(tickers)} 个ticker数据")
       return tickers
       
   except requests.exceptions.RequestException as e:
       logger.error(f"网络请求失败: {e}")
       return {}
   except Exception as e:
       logger.error(f"获取ticker数据失败: {e}")
       return {}

def calculate_dc_ma_signals(df: pd.DataFrame, ma_period: int, cross_confirm_bars: int = 2, price_position_strict: bool = True) -> Tuple[Optional[dict], int]:
   """计算DC28与MA交叉信号 - 支持可变MA周期"""
   try:
       candle_count = len(df)
       
       # 动态计算最小K线数量要求
       min_candles_needed = max(Config.DC_PERIOD, ma_period) + 10
       
       if candle_count < min_candles_needed:
           return None, candle_count
           
       # 计算技术指标
       high_series = pd.Series(df["high"].astype(float)).reset_index(drop=True)
       low_series = pd.Series(df["low"].astype(float)).reset_index(drop=True)
       close_series = pd.Series(df["close"].astype(float)).reset_index(drop=True)
       
       # 计算DC28通道
       dc_high = high_series.rolling(window=Config.DC_PERIOD).max()
       dc_low = low_series.rolling(window=Config.DC_PERIOD).min()
       dc_mid = (dc_high + dc_low) / 2  # DC28中轨
       
       # 计算指定周期的MA
       ma_line = close_series.rolling(window=ma_period).mean()
       
       # 检查数据有效性
       if dc_mid.isna().all() or ma_line.isna().all():
           return None, candle_count
       
       # 检测交叉信号
       signal_info = {
           "dc_mid_current": dc_mid.iloc[-1],
           "ma_current": ma_line.iloc[-1],
           "ma_period": ma_period,
           "price_current": close_series.iloc[-1],
           "golden_cross": False,
           "death_cross": False,
           "cross_bars_ago": None,
           "price_above_cross": False,
           "price_below_cross": False
       }
       
       # 在最近的几根K线内检测交叉
       for i in range(1, min(cross_confirm_bars + 1, len(dc_mid))):
           if pd.isna(dc_mid.iloc[-(i+1)]) or pd.isna(ma_line.iloc[-(i+1)]) or pd.isna(dc_mid.iloc[-i]) or pd.isna(ma_line.iloc[-i]):
               continue
               
           # 金叉检测：DC28中轨从下方穿过MA向上
           if (dc_mid.iloc[-(i+1)] <= ma_line.iloc[-(i+1)] and dc_mid.iloc[-i] > ma_line.iloc[-i]):
               signal_info["golden_cross"] = True
               signal_info["cross_bars_ago"] = i
               break
               
           # 死叉检测：DC28中轨从上方穿过MA向下  
           elif (dc_mid.iloc[-(i+1)] >= ma_line.iloc[-(i+1)] and dc_mid.iloc[-i] < ma_line.iloc[-i]):
               signal_info["death_cross"] = True
               signal_info["cross_bars_ago"] = i
               break
       
       # 验证价格位置
       cross_point = (signal_info["dc_mid_current"] + signal_info["ma_current"]) / 2
       
       if price_position_strict:
           # 严格验证：要求价格明显在交叉点上方/下方
           threshold = cross_point * 0.001  # 0.1%的阈值
           signal_info["price_above_cross"] = signal_info["price_current"] > (cross_point + threshold)
           signal_info["price_below_cross"] = signal_info["price_current"] < (cross_point - threshold)
       else:
           # 宽松验证
           signal_info["price_above_cross"] = signal_info["price_current"] > cross_point
           signal_info["price_below_cross"] = signal_info["price_current"] < cross_point
       
       return signal_info, candle_count
       
   except Exception as e:
       logger.error(f"DC-MA交叉计算错误: {e}")
       return None, 0

def fetch_candles_wrapper(args) -> tuple:
   """并行获取K线数据的包装函数"""
   base, symbol, granularity = args
   df = fetch_candles(base, symbol, granularity)
   if not df.empty:
       df["symbol"] = symbol
   return symbol, df

def create_statistics_cards(results: List[dict], total_symbols: int):
   """创建统计信息"""
   golden_crosses = len([r for r in results if r["signal_type"] == "金叉"])
   death_crosses = len([r for r in results if r["signal_type"] == "死叉"])
   gainers = len([r for r in results if r["change (%)"] > 0])
   
   col1, col2, col3, col4 = st.columns(4)
   
   with col1:
       st.markdown(f'<div class="metric-card"><h3>📊 总扫描数</h3><h2>{total_symbols}</h2><p>扫描的交易对总数</p></div>', unsafe_allow_html=True)
       
   with col2:
       st.markdown(f'<div class="metric-card"><h3>🟢 金叉信号</h3><h2>{golden_crosses}</h2><p>DC28中轨上穿MA</p></div>', unsafe_allow_html=True)
       
   with col3:
       st.markdown(f'<div class="metric-card"><h3>🔴 死叉信号</h3><h2>{death_crosses}</h2><p>DC28中轨下穿MA</p></div>', unsafe_allow_html=True)
       
   with col4:
       st.markdown(f'<div class="metric-card"><h3>📈 上涨币种</h3><h2>{gainers}</h2><p>24h涨幅 > 0的币种</p></div>', unsafe_allow_html=True)

def create_signal_distribution_chart(results: List[dict]):
   """创建信号分布图表"""
   if not results:
       return None
       
   df = pd.DataFrame(results)
   
   # 信号类型分布饼图
   signal_counts = df['signal_type'].value_counts()
   
   fig = px.pie(
       values=signal_counts.values,
       names=signal_counts.index,
       title="<b>交叉信号分布</b>",
       color_discrete_map={
           "金叉": "#51cf66",
           "死叉": "#ff6b6b"
       }
   )
   
   fig.update_layout(
       template="plotly_dark",
       height=400,
       plot_bgcolor='rgba(0,0,0,0)',
       paper_bgcolor='rgba(0,0,0,0)',
       font_color="#e2e8f0",
       title_font_size=20
   )
   
   return fig

def create_signal_scatter_plot(results: List[dict]):
   """创建信号散点图"""
   if not results:
       return None
       
   df = pd.DataFrame(results)
   
   fig = px.scatter(
       df,
       x="cross_bars_ago",
       y="change (%)",
       color="signal_type",
       title="<b>交叉信号时间 vs 24小时涨跌幅</b>",
       labels={"cross_bars_ago": "交叉发生时间(K线前)", "change (%)": "24h涨跌幅 (%)"},
       hover_data=["symbol"],
       color_discrete_map={
           "金叉": "#51cf66",
           "死叉": "#ff6b6b"
       }
   )
   
   fig.add_hline(y=0, line_dash="dash", line_color="#a0aec0", annotation_text="涨跌分界线")
   
   fig.update_layout(
       template="plotly_dark",
       height=400,
       plot_bgcolor='rgba(0,0,0,0)',
       paper_bgcolor='rgba(0,0,0,0)',
       font_color="#e2e8f0",
       title_font_size=20,
       legend_title_text='信号类型'
   )
   
   return fig

def format_dataframe(df: pd.DataFrame) -> pd.DataFrame:
   """格式化数据框显示"""
   if df.empty:
       return df
       
   # 添加信号图标
   def add_signal_icon(row):
       change = row["change (%)"]
       signal = row["signal_type"]
       
       if signal == "金叉":
           if change > 5:
               icon = "🚀🟢"
           elif change > 0:
               icon = "📈🟢"
           else:
               icon = "📉🟢"
       else:  # 死叉
           if change < -5:
               icon = "💥🔴"
           elif change < 0:
               icon = "📉🔴"
           else:
               icon = "📈🔴"
               
       return f"{icon} {row['symbol']}"
   
   df_formatted = df.copy()
   df_formatted["交易对"] = df.apply(add_signal_icon, axis=1)
   df_formatted["信号类型"] = df_formatted["signal_type"]
   df_formatted["24h涨跌"] = df_formatted["change (%)"].apply(lambda x: f"{x:+.2f}%")
   df_formatted["交叉时间"] = df_formatted["cross_bars_ago"].apply(lambda x: f"{x}根K线前")
   df_formatted["价格位置"] = df_formatted["price_position"]
   df_formatted["K线数"] = df_formatted["k_lines"]
   df_formatted["备注"] = df_formatted["note"]
   
   return df_formatted[["交易对", "信号类型", "24h涨跌", "交叉时间", "价格位置", "K线数", "备注"]]

def scan_symbols(base: str, symbols: List[str], granularity: str, ma_period: int, signal_types: List[str], cross_confirm_bars: int, min_volume: float = 0, price_position_strict: bool = True) -> Tuple[List[dict], dict]:
   """扫描交易对的DC-MA交叉信号 - 支持可变MA周期"""
   start_time = time.time()
   results = []
   
   # 动态计算最小K线数量要求
   min_candles_needed = max(Config.DC_PERIOD, ma_period) + 10
   
   # 获取ticker数据
   with st.spinner("📊 正在获取市场数据..."):
       tickers = fetch_all_tickers(base)
       if not tickers:
           st.warning("⚠️ 无法获取完整的市场数据，将使用默认值")
           tickers = {}
   
   # 进度条容器
   progress_container = st.empty()
   status_container = st.empty()
   
   # 并行获取K线数据
   candle_data = {}
   total_symbols = len(symbols)
   processed = 0
   
   with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
       futures = [executor.submit(fetch_candles_wrapper, (base, symbol, granularity)) for symbol in symbols]
       
       for future in as_completed(futures):
           symbol, df = future.result()
           processed += 1
           
           if not df.empty:
               candle_data[symbol] = df
               
           # 更新进度
           progress = processed / total_symbols
           progress_container.progress(progress, text=f"🔄 获取K线数据: {processed}/{total_symbols}")
           status_container.info(f"⏱️ 正在处理: {symbol}")
   
   # 清除进度显示
   progress_container.empty()
   status_container.empty()
   
   # 处理数据
   with st.spinner("🧮 正在计算交叉信号..."):
       insufficient_data = []
       
       for symbol in symbols:
           try:
               if symbol not in candle_data:
                   continue
                   
               df = candle_data[symbol]
               signal_info, candle_count = calculate_dc_ma_signals(df, ma_period, cross_confirm_bars, price_position_strict)
               
               if signal_info is None:
                   insufficient_data.append(symbol)
                   continue
               
               # 使用默认值如果ticker数据不可用
               ticker_data = tickers.get(symbol, {
                   "change24h": 0, 
                   "volume": 0, 
                   "price": 0
               })
               
               # 应用成交量过滤
               if ticker_data["volume"] < min_volume:
                   continue
               
               # 检查是否有符合条件的交叉信号
               has_golden_cross = signal_info["golden_cross"] and signal_info["price_above_cross"]
               has_death_cross = signal_info["death_cross"] and signal_info["price_below_cross"]
               
               if has_golden_cross and "金叉信号" in signal_types:
                   note = ""
                   if candle_count < min_candles_needed + 20:
                       note = f"数据较少({candle_count}根，建议≥{min_candles_needed + 20}根)"
                   
                   results.append({
                       "symbol": symbol,
                       "signal_type": "金叉",
                       "change (%)": round(ticker_data["change24h"], 2),
                       "cross_bars_ago": signal_info["cross_bars_ago"],
                       "price_position": "上方",
                       "k_lines": candle_count,
                       "note": note,
                       "volume": ticker_data["volume"],
                       "price": ticker_data["price"],
                       "dc_mid": signal_info["dc_mid_current"],
                       "ma_value": signal_info["ma_current"],
                       "ma_period": ma_period
                   })
                   
               elif has_death_cross and "死叉信号" in signal_types:
                   note = ""
                   if candle_count < min_candles_needed + 20:
                       note = f"数据较少({candle_count}根，建议≥{min_candles_needed + 20}根)"
                   
                   results.append({
                       "symbol": symbol,
                       "signal_type": "死叉",
                       "change (%)": round(ticker_data["change24h"], 2),
                       "cross_bars_ago": signal_info["cross_bars_ago"],
                       "price_position": "下方",
                       "k_lines": candle_count,
                       "note": note,
                       "volume": ticker_data["volume"],
                       "price": ticker_data["price"],
                       "dc_mid": signal_info["dc_mid_current"],
                       "ma_value": signal_info["ma_current"],
                       "ma_period": ma_period
                   })
                   
           except Exception as e:
               logger.warning(f"{symbol} 处理失败: {e}")
               continue
   
   scan_stats = {
       "scan_time": time.time() - start_time,
       "total_symbols": total_symbols,
       "processed_symbols": len(candle_data),
       "insufficient_data": len(insufficient_data),
       "results_count": len(results),
       "min_candles_needed": min_candles_needed
   }
   
   return results, scan_stats

def main():
   # 创建页面头部
   create_header()
   
   # 创建侧边栏并获取参数
   timeframe, ma_period, signal_types, cross_confirm_bars, show_charts, min_volume, price_position_strict = create_sidebar()
   
   # 主要内容区域
   col1, col2 = st.columns([3, 1])
   
   with col2:
       # 扫描按钮
       if st.button("🚀 开始扫描", key="scan_button", help=f"点击开始扫描DC28×MA{ma_period}交叉信号", use_container_width=True):
           scan_pressed = True
       else:
           scan_pressed = False
           
       # 显示当前设置
       with st.expander("📋 当前设置", expanded=True):
           st.markdown(f"⏰ **时间框架**: {timeframe}")
           st.markdown(f"📈 **MA周期**: {ma_period}")
           st.markdown(f"🎯 **扫描信号**: {', '.join(signal_types)}")
           st.markdown(f"⏱️ **确认周期**: {cross_confirm_bars}根K线")
           if min_volume > 0:
               st.markdown(f"📊 **最小成交量**: {min_volume:,.0f}")
           st.markdown(f"🎯 **价格验证**: {'严格' if price_position_strict else '宽松'}")
           
       # 使用说明
       with st.expander("📖 使用指南", expanded=True):
           st.markdown(f"""
           **DC28×MA{ma_period}交叉扫描器**用于检测唐奇安通道与移动平均线的交叉信号：
           
           - 🟢 **金叉信号**: DC28中轨上穿MA{ma_period} + 价格在交叉点上方 = 看涨
           - 🔴 **死叉信号**: DC28中轨下穿MA{ma_period} + 价格在交叉点下方 = 看跌
           
           **高级功能**:
           - ⏱️ 时间确认(1-5根K线)
           - 📊 成交量过滤
           - 🎨 图表分析
           - 📁 数据导出
           
           **风险提示**:
           - 交叉信号存在滞后性
           - 震荡行情中可能产生假信号
           - 请结合其他指标确认
           """)
   
   with col1:
       if not scan_pressed:
           # 显示使用说明
           st.markdown(f"""
           <div class="stat-card">
           <h3>🎯 DC28×MA{ma_period} 交叉扫描器</h3>
           <p>本工具是专为加密货币交易者设计的专业分析平台，通过实时扫描Bitget交易所的USDT永续合约，检测唐奇安通道(DC28)中轨与移动平均线(MA)的交叉信号。</p>
           
           <h4>📊 核心指标</h4>
           <ul>
             <li>🔷 <b>DC28通道</b>: 28日唐奇安通道，中轨=(最高价+最低价)/2</li>
             <li>📈 <b>MA{ma_period}均线</b>: {ma_period}日移动平均线，趋势基准线</li>
             <li>⚡ <b>交叉检测</b>: 实时监控两线交叉状态</li>
           </ul>
           
           <h4>🎯 交易信号</h4>
           <ul>
             <li>🟢 <b>金叉信号</b>: DC28中轨上穿MA{ma_period} + 价格在交叉点上方 = 看涨</li>
             <li>🔴 <b>死叉信号</b>: DC28中轨下穿MA{ma_period} + 价格在交叉点下方 = 看跌</li>
             <li>📍 <b>位置确认</b>: 严格验证K线价格位置，避免假信号</li>
           </ul>
           
           <h4>🔧 高级功能</h4>
           <ul>
             <li>⏱️ <b>时间确认</b>: 可设置交叉确认周期(1-5根K线)</li>
             <li>📊 <b>成交量过滤</b>: 排除低流动性币种</li>
             <li>🎨 <b>图表分析</b>: 信号分布和时效性可视化</li>
             <li>📁 <b>数据导出</b>: 支持CSV格式下载</li>
           </ul>
           </div>
           """, unsafe_allow_html=True)
           
           # 示例图表
           st.markdown("### 📈 信号示例")
           example_col1, example_col2 = st.columns(2)
           
           with example_col1:
               # 金叉示例图
               fig_golden = go.Figure()
               fig_golden.add_trace(go.Scatter(x=[1, 2, 3, 4], y=[100, 110, 120, 130], name="DC28中轨", line=dict(color="#00d2ff", width=3)))
               fig_golden.add_trace(go.Scatter(x=[1, 2, 3, 4], y=[120, 115, 110, 125], name=f"MA{ma_period}", line=dict(color="#ff6b6b", width=3)))
               fig_golden.add_trace(go.Scatter(x=[3], y=[115], mode="markers", marker=dict(size=15, color="#51cf66"), name="金叉点"))
               fig_golden.update_layout(title="<b>金叉信号示例</b>", template="plotly_dark", height=300)
               st.plotly_chart(fig_golden, use_container_width=True)
               
           with example_col2:
               # 死叉示例图
               fig_death = go.Figure()
               fig_death.add_trace(go.Scatter(x=[1, 2, 3, 4], y=[130, 120, 110, 100], name="DC28中轨", line=dict(color="#00d2ff", width=3)))
               fig_death.add_trace(go.Scatter(x=[1, 2, 3, 4], y=[110, 115, 120, 105], name=f"MA{ma_period}", line=dict(color="#ff6b6b", width=3)))
               fig_death.add_trace(go.Scatter(x=[3], y=[115], mode="markers", marker=dict(size=15, color="#ff6b6b"), name="死叉点"))
               fig_death.update_layout(title="<b>死叉信号示例</b>", template="plotly_dark", height=300)
               st.plotly_chart(fig_death, use_container_width=True)
           return
   
   if scan_pressed:
       if not signal_types:
           st.error("❌ 请至少选择一种信号类型进行扫描")
           return
           
       try:
           # 获取API端点
           with st.spinner("🔗 连接到Bitget API..."):
               base = get_working_endpoint()
               st.success("✅ API连接成功")
           
           # 获取交易对
           with st.spinner("📋 获取交易对列表..."):
               symbols = get_usdt_symbols(base)
               st.success(f"✅ 找到 {len(symbols)} 个USDT永续合约")
           
           # 执行扫描
           results, scan_stats = scan_symbols(base, symbols, timeframe, ma_period, signal_types, cross_confirm_bars, min_volume, price_position_strict)
           
           # 显示扫描统计
           st.success(f"✅ 扫描完成! 耗时 {scan_stats['scan_time']:.1f} 秒")
           
           if scan_stats['insufficient_data'] > 0:
               st.info(f"ℹ️ 有 {scan_stats['insufficient_data']} 个币种数据不足(需要{scan_stats['min_candles_needed']}+根K线)，已跳过")
           
           # 分类结果
           golden_crosses = sorted([r for r in results if r["signal_type"] == "金叉"], key=lambda x: x["change (%)"], reverse=True)
           death_crosses = sorted([r for r in results if r["signal_type"] == "死叉"], key=lambda x: x["change (%)"])
           
           # 显示统计卡片
           create_statistics_cards(results, scan_stats['total_symbols'])
           
           # 显示结果表格
           current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
           
           # 金叉信号
           if "金叉信号" in signal_types:
               st.markdown(f"### 🟢 金叉信号 (DC28中轨上穿MA{ma_period} - {timeframe})")
               if golden_crosses:
                   golden_df = pd.DataFrame(golden_crosses)
                   formatted_golden = format_dataframe(golden_df)
                   st.dataframe(formatted_golden, use_container_width=True, hide_index=True)
                   
                   # 下载按钮
                   csv_data = golden_df.to_csv(index=False)
                   st.download_button(
                       label="📥 下载金叉信号 CSV",
                       data=csv_data,
                       file_name=f"golden_cross_dc28_ma{ma_period}_{timeframe}_{current_time.replace(' ', '_').replace(':', '-')}.csv",
                       mime="text/csv",
                       key="download_golden"
                   )
               else:
                   st.info("🤔 当前没有符合条件的金叉信号")
           
           # 死叉信号
           if "死叉信号" in signal_types:
               st.markdown(f"### 🔴 死叉信号 (DC28中轨下穿MA{ma_period} - {timeframe})")
               if death_crosses:
                   death_df = pd.DataFrame(death_crosses)
                   formatted_death = format_dataframe(death_df)
                   st.dataframe(formatted_death, use_container_width=True, hide_index=True)
                   
                   # 下载按钮
                   csv_data = death_df.to_csv(index=False)
                   st.download_button(
                       label="📥 下载死叉信号 CSV", 
                       data=csv_data,
                       file_name=f"death_cross_dc28_ma{ma_period}_{timeframe}_{current_time.replace(' ', '_').replace(':', '-')}.csv",
                       mime="text/csv",
                       key="download_death"
                   )
               else:
                   st.info("🤔 当前没有符合条件的死叉信号")
           
           # 图表分析
           if show_charts and results:
               st.markdown("---")
               st.markdown("### 📊 信号分析")
               
               chart_col1, chart_col2 = st.columns(2)
               
               with chart_col1:
                   st.markdown("<div class='plot-container'>", unsafe_allow_html=True)
                   signal_chart = create_signal_distribution_chart(results)
                   if signal_chart:
                       st.plotly_chart(signal_chart, use_container_width=True)
                   st.markdown("</div>", unsafe_allow_html=True)
               
               with chart_col2:
                   st.markdown("<div class='plot-container'>", unsafe_allow_html=True)
                   scatter_chart = create_signal_scatter_plot(results)
                   if scatter_chart:
                       st.plotly_chart(scatter_chart, use_container_width=True)
                   st.markdown("</div>", unsafe_allow_html=True)
               
           # 扫描信息
           with st.expander("ℹ️ 扫描详情"):
               st.write(f"**扫描时间**: {current_time}")
               st.write(f"**处理时间**: {scan_stats['scan_time']:.2f} 秒")
               st.write(f"**总交易对数**: {scan_stats['total_symbols']}")
               st.write(f"**成功处理**: {scan_stats['processed_symbols']}")
               st.write(f"**符合条件**: {scan_stats['results_count']}")
               st.write(f"**数据不足**: {scan_stats['insufficient_data']}")
               st.write(f"**扫描信号**: {', '.join(signal_types)}")
               st.write(f"**确认周期**: {cross_confirm_bars}根K线")
               st.write(f"**MA周期**: {ma_period}")
               
       except Exception as e:
           st.error(f"❌ 扫描过程中发生错误: {str(e)}")
           logger.error(f"扫描错误: {e}")

   # 页脚
   st.markdown("---")
   st.markdown("""
   <div style='text-align: center; color: #a0aec0; padding: 2rem;'>
       <p>📈 DC28×MA 交叉信号扫描器 | 精准捕捉趋势转换机会</p>
       <p>© 2023 鹅的交易工具 | 数据来源: Bitget API</p>
   </div>
   """, unsafe_allow_html=True)

if __name__ == "__main__":
   main()