
import streamlit as st
import pandas as pd, numpy as np
import yfinance as yf
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime
import json

st.set_page_config(page_title="退休財務駕駛艙 Pro", page_icon="📈", layout="wide")
DATA=Path("portfolio_data.json")

def load():
    if DATA.exists():
        try: return json.loads(DATA.read_text(encoding="utf-8"))
        except: pass
    return {
      "holdings":[
        {"name":"VXUS","ticker":"VXUS","market":"US","units":0.0,"price":0.0,"currency":"USD","monthly":0,"enabled":True},
        {"name":"SOXX","ticker":"SOXX","market":"US","units":0.0,"price":0.0,"currency":"USD","monthly":20000,"enabled":True},
        {"name":"00988A","ticker":"00988A.TW","market":"TW","units":0.0,"price":0.0,"currency":"TWD","monthly":20000,"enabled":True},
        {"name":"00830","ticker":"00830.TW","market":"TW","units":0.0,"price":0.0,"currency":"TWD","monthly":0,"enabled":True},
        {"name":"路博邁台灣5G基金","ticker":"","market":"FUND","units":0.0,"price":0.0,"currency":"TWD","monthly":0,"enabled":True},
        {"name":"聯博美國成長基金","ticker":"","market":"FUND","units":0.0,"price":0.0,"currency":"TWD","monthly":0,"enabled":True}],
      "fx_usdtwd":31.5,"fx_manual":True,"last_update":None,
      "mortgage":{"principal":8500000,"annual_rate":0.024,"years":20,"extra_payment":0},
      "forecast":{"years":20,"return_rate":0.08,"monthly_contribution_years":10}}
state=st.session_state.setdefault("state",load())

def save(): DATA.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")

def quote(ticker):
    if not ticker: return None
    try:
        x=yf.Ticker(ticker)
        try:
            p=x.fast_info.get("last_price")
            if p is not None: return float(p)
        except: pass
        h=x.history(period="5d",auto_adjust=False)
        if len(h): return float(h["Close"].dropna().iloc[-1])
    except: pass
    return None

def refresh():
    n=0
    for h in state["holdings"]:
        if h.get("enabled",True) and h.get("ticker"):
            p=quote(h["ticker"])
            if p is not None: h["price"]=p; n+=1
    state["last_update"]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save()
    return n

def df_hold():
    fx=float(state.get("fx_usdtwd",31.5)); rows=[]
    for h in state["holdings"]:
        v=float(h.get("units",0) or 0)*float(h.get("price",0) or 0)
        twd=v if h.get("currency")=="TWD" else v*fx
        rows.append({**h,"市值(TWD)":twd})
    return pd.DataFrame(rows)

def mortgage(p,rate,years,extra=0):
    n=years*12; r=rate/12
    pay=p/n if r==0 else p*r*(1+r)**n/((1+r)**n-1)
    bal=p; rows=[]
    for m in range(1,n+1):
        interest=bal*r
        principal=min(bal,max(0,pay-interest+extra))
        bal=max(0,bal-principal)
        rows.append([m,pay+extra,interest,principal,bal])
        if bal<=0: break
    return pd.DataFrame(rows,columns=["month","payment","interest","principal","balance"]),pay

def forecast(initial,monthly,years,rate,contrib_years):
    v=initial; r=rate/12; rows=[]
    for m in range(1,years*12+1):
        v=v*(1+r)+(monthly if m<=contrib_years*12 else 0)
        if m%12==0: rows.append([m//12,v])
    return pd.DataFrame(rows,columns=["year","asset"])

st.title("📊 退休財務駕駛艙 Pro")
st.caption("整合你提供的兩張圖：個股表現／報酬日曆／走勢分析；並可修改標的、Ticker、單位數與每月投入。")

with st.sidebar:
    st.header("行情")
    if st.button("🔄 更新即時/最新可取得行情",use_container_width=True):
        with st.spinner("更新中…"):
            n=refresh()
        st.success(f"已更新 {n} 個可取得行情標的")
        st.rerun()
    state["fx_usdtwd"]=st.number_input("USD/TWD",value=float(state.get("fx_usdtwd",31.5)),step=0.01)
    save()
    st.caption("行情資料可能有延遲；基金淨值若無公開 ticker，請手動輸入。")

t1,t2,t3,t4,t5=st.tabs(["資產總覽","個股表現","走勢分析","20年資產曲線","標的/單位數"])

with t1:
    d=df_hold(); total=d["市值(TWD)"].sum()
    c=st.columns(4)
    c[0].metric("證券資產",f"${total:,.0f}")
    c[1].metric("持股數",f"{len(d)}")
    c[2].metric("每月投入",f"${d['monthly'].sum():,.0f}")
    c[3].metric("USD/TWD",f"{state['fx_usdtwd']:.2f}")
    x=d.copy(); x["占比"]=np.where(total,x["市值(TWD)"]/total,0)
    x["占比"]=x["占比"].map(lambda z:f"{z:.1%}")
    x["市值(TWD)"]=x["市值(TWD)"].map(lambda z:f"${z:,.0f}")
    st.dataframe(x[["name","ticker","units","price","currency","市值(TWD)","占比","monthly"]],use_container_width=True,hide_index=True)
    fig=go.Figure(go.Pie(labels=d["name"],values=d["市值(TWD)"],hole=.45))
    fig.update_layout(title="目前資產配置")
    st.plotly_chart(fig,use_container_width=True)

with t2:
    st.subheader("個股表現")
    period=st.selectbox("期間",["1mo","3mo","6mo","1y","3y","5y"],index=2)
    tickers=[h["ticker"] for h in state["holdings"] if h.get("ticker")]
    sel=st.multiselect("標的",tickers,default=tickers[:6])
    if sel:
        raw=yf.download(sel,period=period,auto_adjust=False,progress=False)["Close"]
        if isinstance(raw,pd.Series): raw=raw.to_frame()
        fig=go.Figure()
        for col in raw.columns:
            s=raw[col].dropna()
            if len(s): fig.add_trace(go.Scatter(x=s.index,y=s/s.iloc[0]*100,name=str(col),mode="lines"))
        fig.update_layout(title="標準化走勢（起點=100）",hovermode="x unified")
        st.plotly_chart(fig,use_container_width=True)
    st.info("若你希望完全複製截圖中的「近1日／近5日／近20日／今年以來」與「報酬日曆」，可在後續接入你指定的行情 API；Yahoo Finance 對部分台股/基金資料並不保證提供完全一致的即時欄位。")

with t3:
    st.subheader("走勢分析")
    period=st.selectbox("走勢期間",["1mo","3mo","6mo","1y","3y","5y"],index=2,key="trend_period")
    sel=st.multiselect("比較", [h["ticker"] for h in state["holdings"] if h.get("ticker")],
                       default=[h["ticker"] for h in state["holdings"] if h.get("ticker")][:6],key="trend_sel")
    if sel:
        raw=yf.download(sel,period=period,auto_adjust=False,progress=False)["Close"]
        if isinstance(raw,pd.Series): raw=raw.to_frame()
        fig=go.Figure()
        for col in raw.columns:
            s=raw[col].dropna()
            if len(s): fig.add_trace(go.Scatter(x=s.index,y=s/s.iloc[0]*100,name=str(col),mode="lines"))
        fig.update_layout(title="資產走勢比較",hovermode="x unified",yaxis_title="標準化")
        st.plotly_chart(fig,use_container_width=True)

with t4:
    st.subheader("20年資產成長曲線")
    d=df_hold(); initial=d["市值(TWD)"].sum(); monthly=d["monthly"].sum()
    a,b,c=st.columns(3)
    years=a.slider("預測年數",1,30,20)
    contrib_years=b.slider("每月投入持續年數",0,30,10)
    rates=c.multiselect("情境",["保守 6%","基準 8%","樂觀 10%"],["保守 6%","基準 8%","樂觀 10%"])
    fig=go.Figure()
    for label in rates:
        rate=float(label.split()[1].replace("%",""))/100
        f=forecast(initial,monthly,years,rate,contrib_years)
        fig.add_trace(go.Scatter(x=f.year,y=f.asset,mode="lines+markers",name=label))
    fig.update_layout(title=f"目前 ${initial:,.0f} + 每月 ${monthly:,.0f}",xaxis_title="第N年",yaxis_title="資產(TWD)",hovermode="x unified")
    st.plotly_chart(fig,use_container_width=True)
    if "基準 8%" in rates:
        f=forecast(initial,monthly,years,.08,contrib_years)
        show=f.copy(); show["資產"]=show.asset.map(lambda z:f"${z:,.0f}")
        show["累積投入"]=(initial+monthly*12*np.minimum(show.year,contrib_years)).map(lambda z:f"${z:,.0f}")
        st.dataframe(show[["year","資產","累積投入"]],use_container_width=True,hide_index=True)

with t5:
    st.subheader("⚙️ 可新增／刪除／修改標的與單位數")
    st.caption("Ticker 可直接改。US ETF：SOXX、VXUS；台股常見格式：00830.TW。基金若沒有公開 ticker，保留空白並直接填「價格/淨值」。")
    ed=st.data_editor(pd.DataFrame(state["holdings"]),num_rows="dynamic",use_container_width=True,hide_index=True,
        column_config={
            "enabled":st.column_config.CheckboxColumn("啟用"),
            "units":st.column_config.NumberColumn("單位數",min_value=0.0,step=1.0),
            "price":st.column_config.NumberColumn("價格/淨值",min_value=0.0,step=0.01),
            "monthly":st.column_config.NumberColumn("每月投入(TWD)",min_value=0.0,step=1000.0)
        })
    if st.button("💾 儲存修改",type="primary"):
        state["holdings"]=ed.fillna("").to_dict("records"); save(); st.success("已儲存"); st.rerun()

st.divider()
st.caption("⚠️ 本工具為退休財務規劃試算，不構成投資建議。即時行情的實際延遲取決於資料供應商；基金淨值可能需手動更新。")
