"""展示层：读取 analysis.json → 生成单文件 report.html（数据内联）。

用法:
    python3 build_report.py [--input data/analysis.json] [--out report.html]
                            [--title 近期麦门报告]
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fmt_hour(h: int) -> str:
    return f"{h:02d}时" if h else "24时"


def build_html(a: dict, title: str) -> str:
    hours = a["stats"]["hourHistogram"]
    max_hour = max(hours) or 1
    hour_bars = "".join(
        f'<div class="bar-wrap"><i class="bar" style="--h:{round(v / max_hour * 100)}%;--i:{h}"'
        f' title="{fmt_hour(h)} · {v}单"></i><s>{h%24 if h else 24}</s></div>'
        for h, v in enumerate(hours)
    )
    # 星期从周一开始显示
    wd = a["stats"]["weekdayHistogram"]
    max_wd = max(wd) or 1
    wd_bars = "".join(
        f'<div class="wd"><span class="wd-bar" style="--h:{round(v / max_wd * 100)}%;--i:{i}"></span>'
        f'<s>{"一二三四五六日"[i]}</s></div>'
        for i, v in enumerate(wd)
    )
    take = a["takeWayBreakdown"]
    take_total = sum(take.values()) or 1
    take_rows = "".join(
        f'<div class="kv"><span>{k or "未知"}</span>'
        f'<div class="kv-bar"><i style="--w:{round(v / take_total * 100)}%"></i></div>'
        f"<b>{v}单</b></div>"
        for k, v in take.items()
    )
    stores_sorted = sorted(a["storeBreakdown"].items(), key=lambda x: -x[1])
    store_rows = "".join(
        f'<div class="store-row"><span class="rank">{i+1}</span>'
        f"<span class='sname'>{name}</span><b>{c} 单</b></div>"
        for i, (name, c) in enumerate(stores_sorted[:5])
    )
    subs = "".join(
        f'<div class="sub-tag"><b>{s["name"]}</b><span>{s["line"]}</span></div>'
        for s in a.get("subPersonas", [])
    )
    events = "".join(
        f'<div class="event">{e["title"]}</div>' for e in a.get("events", [])
    ) or '<div class="event">暂无进行中的活动</div>'
    period_txt = f'{a["period"]["from"]} ~ {a["period"]["to"]}'

    kcal_note = '（含估算项）' if a.get("kcalEstimated") else ''
    data_json = json.dumps({
        "persona": a["persona"], "orderCount": a["orderCount"],
        "totalSpend": a["totalSpend"],
    }, ensure_ascii=False)

    script_js = """
const screens=[...document.querySelectorAll('.screen')];
const dots=[...document.querySelectorAll('.dots a')];
const progress=document.getElementById('progress');

// 背景装饰：巨型编号 + 漂浮元素（注入式，保持 HTML 干净）
screens.forEach((s,idx)=>{
  const giant=document.createElement('div');
  giant.className='giant';
  giant.textContent=String(idx+1).padStart(2,'0');
  s.appendChild(giant);
  const fx1=document.createElement('div');
  fx1.className='fx fx-arch';
  fx1.textContent='M';
  fx1.style.cssText=`top:${8+((idx*37)%18)}%;${idx%2?'left':'right'}:${6+((idx*23)%10)}%;--r:${(idx%2?8:-10)}deg`;
  s.appendChild(fx1);
  const fx2=document.createElement('div');
  fx2.className='fx fx-dot'+(idx%3?'':' g');
  fx2.style.cssText=`bottom:${14+((idx*17)%22)}%;${idx%2?'right':'left'}:${8+((idx*31)%12)}%;animation-delay:${(idx*.7)%3}s`;
  s.appendChild(fx2);
  if(idx%3===1){
    const f=document.createElement('div');
    f.className='fx fx-fries';
    f.style.cssText=`top:${18+((idx*13)%30)}%;right:${12+((idx*19)%14)}%;`;
    s.appendChild(f);
  }
});

// 数字滚动
function countUp(el){
  if(el.dataset.done) return;
  el.dataset.done=1;
  const text=el.textContent;
  const m=text.match(/^[^\\d]*([\\d.,]+)[^\\d]*$/);
  if(!m) return;
  const target=parseFloat(m[1].replace(/,/g,''));
  if(!isFinite(target)) return;
  const pre=text.slice(0,text.indexOf(m[1]));
  const suf=text.slice(text.indexOf(m[1])+m[1].length);
  const dur=1100, t0=performance.now();
  function tick(t){
    const p=Math.min((t-t0)/dur,1);
    const ease=1-Math.pow(1-p,3);
    const val=target>=1000 ? Math.round(target*ease).toLocaleString()
                           : (target%1?(target*ease).toFixed(1):Math.round(target*ease));
    el.textContent=pre+val+suf;
    if(p<1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

const io=new IntersectionObserver(es=>es.forEach(e=>{
  if(e.isIntersecting){
    e.target.classList.add('on');
    const i=screens.indexOf(e.target);
    dots.forEach((d,j)=>d.classList.toggle('on',j===i));
    e.target.querySelectorAll('.big,.mid,.pstats b').forEach((el,k)=>{
      el.classList.add('pop'); el.style.setProperty('--d',(k*.15)+'s');
      setTimeout(()=>countUp(el),200+k*150);
    });
  }
}),{threshold:.55});
screens.forEach(s=>io.observe(s));

// 顶部进度条
const deck=document.querySelector('.deck');
deck.addEventListener('scroll',()=>{
  const p=deck.scrollTop/(deck.scrollHeight-deck.clientHeight);
  progress.style.width=(p*100)+'%';
},{passive:true});

setTimeout(()=>document.querySelector('.hint').style.opacity=0,5000);
console.log('麦门人格报告', __DATA__);
""".replace("__DATA__", data_json)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title} · {a['persona']}</title>
<style>
:root {{ --gold:#FFC72C; --red:#DA291C; --bg:#141414; --card:#1e1e1e; --tx:#f5f0e6; --sub:#9b948a; }}
* {{ margin:0; padding:0; box-sizing:border-box; -webkit-tap-highlight-color:transparent; }}
html {{ scroll-behavior:smooth; }}
body {{ background:var(--bg); color:var(--tx); font-family:-apple-system,"PingFang SC","Noto Sans SC",sans-serif; }}
.deck {{ scroll-snap-type:y mandatory; overflow-y:scroll; height:100dvh; }}
.screen {{ scroll-snap-align:start; min-height:100dvh; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; padding:8vh 24px; position:relative; overflow:hidden; opacity:0; transform:translateY(24px) scale(.97); transition:opacity .7s ease,transform .7s ease; }}
.screen.on {{ opacity:1; transform:none; }}
.kicker {{ font-size:13px; letter-spacing:.35em; color:var(--gold); text-transform:uppercase; margin-bottom:14px; }}
h1 {{ font-size:clamp(30px,8vw,52px); font-weight:800; line-height:1.25; }}
h2 {{ font-size:clamp(24px,6vw,40px); font-weight:800; line-height:1.3; }}
.big {{ font-size:clamp(56px,18vw,120px); font-weight:900; color:var(--gold); line-height:1.05; }}
.mid {{ font-size:clamp(36px,11vw,72px); font-weight:900; color:var(--gold); line-height:1.1; }}
p.lead {{ color:var(--sub); font-size:15px; margin-top:14px; line-height:1.7; }}
.accent {{ color:var(--gold); }}
.panel {{ width:100%; max-width:480px; background:var(--card); border-radius:20px; padding:22px 20px; margin-top:26px; text-align:left; }}
.kv {{ display:flex; align-items:center; gap:10px; margin:10px 0; font-size:14px; }}
.kv>span {{ width:72px; color:var(--sub); flex:none; }}
.kv b {{ flex:none; color:var(--tx); }}
.kv-bar {{ flex:1; height:8px; background:#333; border-radius:99px; overflow:hidden; }}
.kv-bar i {{ display:block; height:100%; width:var(--w,0%); background:var(--gold); border-radius:99px; }}
.bars {{ display:flex; gap:3px; align-items:flex-end; height:120px; width:100%; max-width:480px; margin-top:26px; }}
.bar-wrap {{ flex:1; display:flex; flex-direction:column; align-items:center; gap:6px; height:100%; justify-content:flex-end; }}
.bar {{ width:100%; height:var(--h,0%); background:linear-gradient(180deg,var(--gold),var(--red)); border-radius:4px 4px 2px 2px; min-height:4px; }}
.bar-wrap s {{ font-size:10px; color:var(--sub); text-decoration:none; }}
.wds {{ display:flex; gap:8px; align-items:flex-end; height:90px; margin-top:20px; }}
.wd {{ flex:1; display:flex; flex-direction:column; align-items:center; gap:6px; height:100%; justify-content:flex-end; }}
.wd-bar {{ width:70%; height:var(--h,0%); background:var(--gold); border-radius:4px; min-height:4px; }}
.wd s {{ font-size:11px; color:var(--sub); text-decoration:none; }}
.store-row {{ display:flex; align-items:center; gap:10px; padding:10px 0; border-bottom:1px solid #2c2c2c; font-size:14px; }}
.store-row:last-child {{ border-bottom:none; }}
.rank {{ width:22px; height:22px; flex:none; border-radius:6px; background:var(--gold); color:#141414; font-weight:800; font-size:12px; display:flex; align-items:center; justify-content:center; }}
.sname {{ flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.persona-card {{ width:min(84vw,340px); aspect-ratio:9/16; border-radius:28px; padding:34px 26px; display:flex; flex-direction:column; justify-content:space-between; text-align:left; background:linear-gradient(160deg,#DA291C 0%,#a81410 55%,#5c0a08 100%); box-shadow:0 24px 60px rgba(218,41,28,.35); }}
.persona-card .brand {{ font-size:12px; letter-spacing:.3em; color:var(--gold); }}
.persona-card h2 {{ font-size:clamp(30px,9vw,44px); font-weight:900; line-height:1.2; }}
.persona-card .line {{ color:rgba(255,255,255,.85); font-size:15px; margin-top:12px; line-height:1.6; }}
.pstats {{ display:flex; gap:18px; margin-top:20px; }}
.pstats div b {{ display:block; font-size:22px; font-weight:900; color:var(--gold); }}
.pstats div s {{ text-decoration:none; font-size:11px; color:rgba(255,255,255,.7); }}
.sub-tag {{ background:rgba(0,0,0,.28); border:1px solid rgba(255,199,44,.4); border-radius:12px; padding:10px 12px; margin-top:10px; font-size:13px; }}
.sub-tag b {{ color:var(--gold); margin-right:8px; }}
.event {{ background:var(--card); border-radius:12px; padding:12px 14px; margin-top:10px; font-size:13px; color:var(--tx); text-align:left; line-height:1.5; }}
.dots {{ position:fixed; right:12px; top:50%; transform:translateY(-50%); display:flex; flex-direction:column; gap:8px; z-index:9; }}
.dots a {{ width:6px; height:6px; border-radius:99px; background:#4a4a4a; transition:.3s; }}
.dots a.on {{ background:var(--gold); height:18px; }}
.hint {{ position:fixed; bottom:18px; left:50%; transform:translateX(-50%); font-size:12px; color:var(--sub); z-index:9; animation:bob 1.6s ease-in-out infinite; }}
@keyframes bob {{ 50% {{ transform:translate(-50%,6px); }} }}
.foot {{ font-size:11px; color:var(--sub); margin-top:30px; }}

/* ---------- 动效层 ---------- */
.deck {{ scroll-behavior:smooth; }}
.screen {{ will-change:transform,opacity; }}
.screen.on {{ transition:opacity .8s cubic-bezier(.2,.8,.2,1),transform .8s cubic-bezier(.2,.8,.2,1); }}
#progress {{ position:fixed; top:0; left:0; height:3px; width:0; background:linear-gradient(90deg,var(--gold),var(--red)); z-index:99; transition:width .15s linear; }}
.giant {{ position:absolute; inset:auto 0 12% 0; text-align:center; font-size:clamp(80px,26vw,180px); font-weight:900; line-height:1; color:transparent; -webkit-text-stroke:1.5px rgba(255,199,44,.10); pointer-events:none; user-select:none; letter-spacing:.05em; white-space:nowrap; overflow:hidden; }}
.fx {{ position:absolute; pointer-events:none; opacity:.5; }}
.fx-arch {{ color:rgba(255,199,44,.14); font-weight:900; font-size:64px; animation:floaty 6s ease-in-out infinite; }}
.fx-dot {{ width:10px; height:10px; border-radius:99px; background:rgba(218,41,28,.5); animation:floaty 5s ease-in-out infinite; }}
.fx-dot.g {{ background:rgba(255,199,44,.45); }}
.fx-fries {{ width:12px; height:44px; border-radius:4px; background:linear-gradient(180deg,var(--gold),#e6a91f); transform:rotate(14deg); animation:floaty 7s ease-in-out infinite; }}
@keyframes floaty {{ 0%,100% {{ transform:translateY(0) rotate(var(--r,0deg)); }} 50% {{ transform:translateY(-16px) rotate(var(--r,0deg)); }} }}
.screen .bar {{ height:2%; transition:height 1s cubic-bezier(.2,.8,.25,1); transition-delay:calc(var(--i,0)*45ms); }}
.screen.on .bar {{ height:var(--h,0%); }}
.screen .wd-bar {{ height:2%; transition:height .9s cubic-bezier(.2,.8,.25,1); transition-delay:calc(var(--i,0)*60ms); }}
.screen.on .wd-bar {{ height:var(--h,0%); }}
.kv-bar i {{ width:0; transition:width 1s cubic-bezier(.2,.8,.25,1) .3s; }}
.screen.on .kv-bar i {{ width:var(--w,0%); }}
.num {{ display:inline-block; }}
.shine {{ position:relative; overflow:hidden; }}
.shine::after {{ content:""; position:absolute; top:-60%; left:-80%; width:60%; height:220%; background:linear-gradient(105deg,transparent,rgba(255,255,255,.22),transparent); transform:rotate(10deg); animation:sweep 4.5s ease-in-out infinite; }}
@keyframes sweep {{ 0%,60% {{ left:-80%; }} 100% {{ left:140%; }} }}
.persona-card {{ animation:cardfloat 5s ease-in-out infinite; }}
@keyframes cardfloat {{ 0%,100% {{ transform:translateY(0) rotate(-1deg); }} 50% {{ transform:translateY(-10px) rotate(1deg); }} }}
.pop {{ display:inline-block; animation:pop .7s cubic-bezier(.2,1.4,.3,1) both; animation-delay:var(--d,0s); }}
@keyframes pop {{ from {{ transform:scale(.4); opacity:0; }} to {{ transform:scale(1); opacity:1; }} }}
@media (prefers-reduced-motion:reduce) {{ * {{ animation:none !important; transition:none !important; }} }}
</style>
</head>
<body>
<div id="progress"></div>
<nav class="dots" aria-hidden="true">{"".join(f'<a href="#s{i}"></a>' for i in range(1,10))}</nav>
<div class="hint">↓ 滑动开启报告</div>
<main class="deck">

<section class="screen" id="s1">
  <p class="kicker">{title}</p>
  <h1>2026，你和麦当劳的<br><span class="accent">{a['orderCount']}</span> 次相遇</h1>
  <p class="lead">{period_txt}<br>一共 {a['orderCount']} 单 · {a['totalSpend']} 元 · {a['storeCount']} 家门店</p>
</section>

<section class="screen" id="s2">
  <p class="kicker">总览</p>
  <h2>这段日子<br>你花了 <span class="mid">{a['totalSpend']}</span> 元</h2>
  <div class="panel">{take_rows}
    <div class="kv"><span>平均每单</span><div class="kv-bar"><i style="--w:40%"></i></div><b>{a['avgSpend']} 元</b></div>
  </div>
</section>

<section class="screen" id="s3">
  <p class="kicker">本命单品</p>
  <h2>你点了 <span class="mid">{a['stats']['topItemOrderCount']}</span> 次</h2>
  <h1 class="accent" style="margin-top:6px">{a['stats']['topItemName']}</h1>
  <p class="lead">它出现在你 {round(a['stats']['topItemRatio']*100)}% 的订单里<br>别人在探索菜单，你在守护唯一</p>
</section>

<section class="screen" id="s4">
  <p class="kicker">时间画像</p>
  <h2>你最常在这个时候<br>想念麦当劳</h2>
  <div class="bars">{hour_bars}</div>
  <p class="lead">横轴 0-23 点 · 柱高为下单量</p>
</section>

<section class="screen" id="s5">
  <p class="kicker">热量换算</p>
  <div class="big">{a['totalKcal']}</div>
  <h2 style="margin-top:8px">大卡{kcal_note}</h2>
  <p class="lead">大约相当于 <span class="accent"><b>{a['riceBowls']}</b></span> 碗米饭<br>没关系，快乐是无价的</p>
  <div class="wds">{wd_bars}</div>
  <p class="lead" style="margin-top:10px">一周中你的麦门时刻分布</p>
</section>

<section class="screen" id="s6">
  <p class="kicker">门店足迹</p>
  <h2>你征服了 <span class="mid">{a['storeCount']}</span> 家门店</h2>
  <div class="panel">{store_rows}</div>
</section>

<section class="screen" id="s7">
  <p class="kicker">省钱成绩</p>
  <h2>优惠帮你省下了</h2>
  <div class="mid" style="margin-top:10px">¥ {a['totalDiscount']}</div>
  <p class="lead">其中用券抵扣 ¥{a['couponSavings']}<br>会省的人，运气都不会太差</p>
</section>

<section class="screen" id="s8">
  <p class="kicker">你的麦门人格</p>
  <div class="persona-card shine">
    <div>
      <div class="brand">MCP WRAPPED · {title}</div>
      <h2 style="margin-top:18px">{a['persona']}</h2>
      <div class="line">{a['personaLine']}</div>
      {subs}
    </div>
    <div class="pstats">
      <div><b>{a['orderCount']}</b><s>订单</s></div>
      <div><b>¥{a['totalSpend']}</b><s>消费</s></div>
      <div><b>{a['storeCount']}</b><s>门店</s></div>
    </div>
  </div>
  <p class="foot">长按或截图，保存你的麦门人格卡</p>
</section>

<section class="screen" id="s9">
  <p class="kicker">下一单彩蛋</p>
  <h2>报告看完<br>该吃点好的了</h2>
  <div class="panel">
    <div class="kv"><span>可用积分</span><div class="kv-bar"><i style="--w:70%"></i></div><b>{a['account']['availablePoint']}</b></div>
    <div class="kv"><span>即将过期</span><div class="kv-bar"><i style="--w:12%"></i></div><b style="color:var(--red)">{a['account']['expiringPoint']}</b></div>
  </div>
  <p class="lead" style="align-self:flex-start;width:100%;max-width:480px;text-align:left;margin-top:22px">本月别错过</p>
  <div style="width:100%;max-width:480px">{events}</div>
  <p class="foot">数据来自麦当劳 MCP · 仅本地处理 · 不含个人敏感信息<br>用 AI 生成于 WorkBuddy · 麦门！</p>
</section>

</main>
<script>__SCRIPT__</script>
</body>
</html>""".replace("__SCRIPT__", script_js)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(ROOT / "data" / "analysis.json"))
    ap.add_argument("--out", default=str(ROOT / "report.html"))
    ap.add_argument("--title", default="近期麦门报告")
    args = ap.parse_args()
    a = json.loads(Path(args.input).read_text())
    Path(args.out).write_text(build_html(a, args.title), encoding="utf-8")
    print(f"完成 → {args.out}")


if __name__ == "__main__":
    main()
