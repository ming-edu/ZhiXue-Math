/* 智学数学 · AI Key 设置面板（纯静态版）
 * 自动在页面注入「AI设置」入口与弹窗。Key 只存本人浏览器，不上传、不共享。
 */
(function () {
  'use strict';

  function ensureStyle(){
    if(document.getElementById('aiSetStyle')) return;
    var s=document.createElement('style');
    s.id='aiSetStyle';
    s.textContent =
      '.ai-key-btn{cursor:pointer;user-select:none}'+
      '.ai-status-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;vertical-align:middle}'+
      '.ai-status-dot.on{background:#22c55e}.ai-status-dot.off{background:#f59e0b}'+
      '.ai-mask{position:fixed;inset:0;background:rgba(20,24,60,.5);backdrop-filter:blur(4px);z-index:2000;display:none;align-items:center;justify-content:center;padding:20px}'+
      '.ai-box{background:#fff;border-radius:16px;box-shadow:0 20px 60px rgba(20,24,60,.25);width:min(480px,96vw);padding:26px;animation:aiIn .25s ease}'+
      '@keyframes aiIn{from{opacity:0;transform:translateY(12px) scale(.98)}to{opacity:1;transform:none}}'+
      '.ai-box h3{font-size:18px;font-weight:800;margin:0 0 6px;display:flex;align-items:center;gap:8px}'+
      '.ai-box p.sub{font-size:12.5px;color:#64748b;margin:0 0 18px;line-height:1.6}'+
      '.ai-box label{display:block;font-size:12.5px;font-weight:700;margin:14px 0 6px;color:#334155}'+
      '.ai-box input{width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #dbe2ea;border-radius:9px;font-size:14px;font-family:ui-monospace,monospace}'+
      '.ai-box input:focus{outline:none;border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.12)}'+
      '.ai-box .adv{display:none}'+
      '.ai-box .adv.show{display:block}'+
      '.ai-box .row{display:flex;gap:10px;align-items:center;margin-top:20px;flex-wrap:wrap}'+
      '.ai-btn{padding:10px 16px;border:none;border-radius:9px;font-size:13px;font-weight:700;cursor:pointer}'+
      '.ai-btn.primary{background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff}'+
      '.ai-btn.ghost{background:#f1f5f9;color:#475569}'+
      '.ai-btn.link{background:none;color:#6366f1;padding:6px 0;font-size:12px}'+
      '.ai-msg{font-size:12.5px;margin-top:12px;min-height:18px;line-height:1.5}';
    document.head.appendChild(s);
  }

  function iconSvg(name){
    // 复用页面 sprite；若不存在则用内联兜底
    return '<svg class="icon" style="width:16px;height:16px"><use href="#i-key"></use></svg>';
  }

  function inject(){
    ensureStyle();
    if(document.getElementById('aiKeyBtn')) return;

    // 注入按钮到顶栏导航
    var nav = document.querySelector('.topbar nav');
    var btn = document.createElement('a');
    btn.id='aiKeyBtn';
    btn.className='ai-key-btn';
    btn.href='javascript:void(0)';
    btn.innerHTML='<span class="ai-status-dot '+(window.AI&&AI.hasKey()?'on':'off')+'" id="aiDot"></span>'+
                  '<svg class="icon"><use href="#i-sparkles"></use></svg>AI设置';
    if(nav) nav.appendChild(btn);
    else{
      var logo=document.querySelector('.topbar .logo');
      if(logo) logo.parentNode.appendChild(btn);
    }

    // 注入弹窗
    var mask=document.createElement('div');
    mask.id='aiSetMask';
    mask.className='ai-mask';
    var cfg=(window.AI?AI.getCfg():{});
    var curKey=(window.AI?AI.getKey():'');
    mask.innerHTML =
      '<div class="ai-box">'+
        '<h3>'+iconSvg('key')+'AI 设置</h3>'+
        '<p class="sub">拍照识题和整页批改会调用 AI，需要你自己的硅基流动 API Key。<br>'+
        '默认使用<b>永久免费的视觉模型</b>（Qwen2.5-VL-7B），识图批改不花钱。<br>'+
        'Key 只保存在你这台设备的浏览器里，不上传、不与他人共享。规则判分不需要 Key。</p>'+
        '<label>API Key（sk-...）</label>'+
        '<input id="aiKeyInput" type="password" placeholder="粘贴你的硅基流动 API Key" value="'+escapeAttr(curKey)+'">'+
        '<a href="javascript:void(0)" class="ai-btn link" onclick="document.getElementById(\'aiAdv\').classList.toggle(\'show\')">高级：接口地址 / 模型</a>'+
        '<div class="adv" id="aiAdv">'+
          '<label>接口地址 Base URL</label>'+
          '<input id="aiBaseInput" value="'+escapeAttr(cfg.base_url||'https://api.siliconflow.cn/v1')+'">'+
          '<label>模型名（默认免费视觉模型，可识别作业图片）</label>'+
          '<input id="aiModelInput" value="'+escapeAttr(cfg.model||'Qwen/Qwen2.5-VL-7B-Instruct')+'">'+
        '</div>'+
        '<div class="row">'+
          '<button class="ai-btn primary" id="aiSaveBtn">保存</button>'+
          '<button class="ai-btn ghost" onclick="document.getElementById(\'aiSetMask\').style.display=\'none\'">关闭</button>'+
          '<a href="https://cloud.siliconflow.cn/account/ak" target="_blank" rel="noopener" class="ai-btn link" style="margin-left:auto">去申请免费 Key →</a>'+
        '</div>'+
        '<div class="ai-msg" id="aiMsg"></div>'+
      '</div>';
    document.body.appendChild(mask);

    btn.addEventListener('click', function(){
      mask.style.display='flex';
      if(window.AI){ document.getElementById('aiKeyInput').value=AI.getKey(); }
    });
    mask.addEventListener('click', function(e){ if(e.target===mask) mask.style.display='none'; });
    document.getElementById('aiSaveBtn').addEventListener('click', function(){
      if(!window.AI){ msg('AI 模块未加载','err'); return; }
      var k=document.getElementById('aiKeyInput').value.trim();
      if(k && k.indexOf('sk-')!==0){ msg('Key 通常以 sk- 开头，请检查','err'); return; }
      AI.setKey(k);
      AI.setCfg({
        base_url: document.getElementById('aiBaseInput').value.trim()||'https://api.siliconflow.cn/v1',
        model: document.getElementById('aiModelInput').value.trim()||'Qwen/Qwen2.5-VL-7B-Instruct'
      });
      var dot=document.getElementById('aiDot');
      if(dot) dot.className='ai-status-dot '+(k?'on':'off');
      msg(k?'已保存。现在可以使用拍照识题和整页批改了。':'已清空 Key，AI 功能将不可用','ok');
    });
    function msg(t,type){
      var el=document.getElementById('aiMsg');
      el.textContent=t;
      el.style.color=type==='err'?'#dc2626':'#16a34a';
    }
  }
  function escapeAttr(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;'); }

  // sprite 里补一个 key 图标（若页面未定义则动态加）
  function ensureKeyIcon(){
    var sprite=document.querySelector('svg[style*="display: none"], svg[xmlns]');
    var sym=document.getElementById('i-key');
    if(sym) return;
    // 在 body 首个 svg sprite 中追加 symbol；找不到则跳过（按钮用 sparkles 兜底）
    var sprites=document.querySelectorAll('svg');
    for(var i=0;i<sprites.length;i++){
      var defs=sprites[i].querySelector('defs') || (sprites[i].querySelectorAll('symbol').length?sprites[i]:null);
      if(defs){
        var s=document.createElementNS('http://www.w3.org/2000/svg','symbol');
        s.setAttribute('id','i-key'); s.setAttribute('viewBox','0 0 24 24');
        s.innerHTML='<g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="15" r="4"/><path d="m11 12 8-8 2 2-2 2 2 2-3 3-2-2-2 2"/></g>';
        defs.appendChild(s); break;
      }
    }
  }

  function init(){
    if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', function(){ ensureKeyIcon(); inject(); });
    else{ ensureKeyIcon(); inject(); }
  }
  init();

  // 暴露一个手动打开方法，供"未配置Key"时引导
  window.openAISettings=function(){ inject(); document.getElementById('aiSetMask').style.display='flex'; };
})();
