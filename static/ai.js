/* 智学数学 · 前端 AI 直连模块（纯静态版）
 * 每个使用者填自己的硅基流动 API Key，存在本人浏览器 localStorage，谁用谁出，互不共享。
 * 判分(judge)为纯本地规则，不需要 Key、不花钱；识题/看图批改才需要 Key。
 */
(function (global) {
  'use strict';

  var KEY_STORAGE = 'zhixue_ai_key_v1';
  var CFG_STORAGE = 'zhixue_ai_cfg_v1';
  var DEFAULT_BASE = 'https://api.siliconflow.cn/v1';
  var DEFAULT_MODEL = 'Qwen/Qwen2.5-VL-7B-Instruct';  // 硅基流动永久免费视觉模型，支持识图/OCR/数学题

  function getKey(){ try{ return (localStorage.getItem(KEY_STORAGE)||'').trim(); }catch(e){ return ''; } }
  function setKey(k){ try{ localStorage.setItem(KEY_STORAGE, String(k||'').trim()); return true; }catch(e){ return false; } }
  function getCfg(){
    try{ return JSON.parse(localStorage.getItem(CFG_STORAGE)||'{}'); }catch(e){ return {}; }
  }
  function setCfg(c){ try{ localStorage.setItem(CFG_STORAGE, JSON.stringify(c||{})); }catch(e){} }
  function baseUrl(){ return (getCfg().base_url||DEFAULT_BASE).replace(/\/+$/,''); }
  function model(){ return getCfg().model||DEFAULT_MODEL; }
  function hasKey(){ return !!getKey(); }

  function clone(o){ return JSON.parse(JSON.stringify(o)); }

  // 图片文件 -> data URL
  function imgToDataUrl(file){
    return new Promise(function(resolve, reject){
      var r = new FileReader();
      r.onload = function(){ resolve(r.result); };
      r.onerror = function(){ reject(new Error('读取图片失败')); };
      r.readAsDataURL(file);
    });
  }

  // 稳健提取模型输出中的 JSON
  function parseJson(text){
    text = String(text||'').trim();
    var m = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
    if(m) text = m[1].trim();
    var s = text.indexOf('{'), e = text.lastIndexOf('}');
    if(s >= 0 && e > s) text = text.slice(s, e+1);
    try{ return JSON.parse(text); }
    catch(err){ throw new Error('AI 返回内容无法解析，请重试或检查题目是否清晰'); }
  }

  // 调用视觉语言模型
  function callVLM(messages, maxTokens){
    var key = getKey();
    if(!key) throw new Error('请先在右上角「AI设置」中填写你自己的硅基流动 API Key');
    maxTokens = maxTokens || 1500;
    return fetch(baseUrl()+'/chat/completions', {
      method:'POST',
      headers:{ 'Authorization':'Bearer '+key, 'Content-Type':'application/json' },
      body: JSON.stringify({ model: model(), messages: messages, max_tokens: maxTokens, temperature: 0.2 })
    }).then(function(resp){
      if(resp.status===401) throw new Error('API Key 无效或已过期，请在「AI设置」中更换');
      if(resp.status===429) throw new Error('请求过于频繁或额度不足，请稍后再试（额度在你的硅基流动账户）');
      if(!resp.ok) return resp.text().then(function(t){ throw new Error('AI 请求失败('+resp.status+')：'+t.slice(0,120)); });
      return resp.json();
    }).then(function(data){
      var content = data && data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content;
      if(!content) throw new Error('AI 未返回内容，请重试');
      return content;
    });
  }

  // 识题 + 自动解题：返回 {count, questions}
  function parseHomework(file, knowledgePoints){
    if(!file) return Promise.reject(new Error('请先选择作业照片'));
    return imgToDataUrl(file).then(function(dataUrl){
      var kpHint = (knowledgePoints && knowledgePoints.length)
        ? '\n可选知识点（从中选最匹配的一个，没有就填“其他”）：' + knowledgePoints.join('、') : '';
      var prompt = '你是一位小学五年级数学老师。下面是一张作业题照片。请完成：\n'+
        '1. 数出一共有几道题；\n2. 逐题抄录题目原文（保留数字与单位，选择题请列出选项）；\n'+
        '3. 独立解出每题的正确答案；\n4. 用一句话写出每题的解题思路（给老师核对用）；\n'+
        '5. 判断每题题型：choice(选择题)/fill(填空题)/calc(计算或解答题)；\n'+
        '6. 为每题匹配一个知识点。'+kpHint+'\n\n'+
        '严格只返回如下 JSON，不要任何解释文字：\n'+
        '{"count": 题数, "questions": [{"no": 1, "text": "题目原文", "answer": "正确答案", "analysis": "解题思路", "q_type": "calc", "knowledge_point": "知识点名"}]}';
      var messages = [{ role:'user', content:[
        { type:'image_url', image_url:{ url: dataUrl } },
        { type:'text', text: prompt }
      ]}];
      return callVLM(messages, 2000);
    }).then(function(text){
      var result = parseJson(text);
      var qs = result.questions || [];
      var cleaned = [];
      qs.forEach(function(q, i){
        var qt = q.q_type;
        if(['choice','fill','calc'].indexOf(qt)<0) qt='calc';
        cleaned.push({
          no: q.no || (i+1),
          text: String(q.text||'').trim(),
          answer: String(q.answer||'').trim(),
          analysis: String(q.analysis||'').trim(),
          q_type: qt,
          knowledge_point: String(q.knowledge_point||'其他').trim()
        });
      });
      return { count: cleaned.length, questions: cleaned };
    });
  }

  // 直接看学生作业照片逐题批改：返回 {graded:[...]}, 此处只返回原始结果，写库逻辑由页面负责
  function gradePage(file, standardAnswers, knowledgePoints){
    if(!file) return Promise.reject(new Error('请选择整页作业照片'));
    return imgToDataUrl(file).then(function(dataUrl){
      var std = JSON.stringify(standardAnswers || []);
      var kpHint = (knowledgePoints && knowledgePoints.length)
        ? '\n可选知识点（每题选最匹配的一个）：' + knowledgePoints.join('、') : '';
      var prompt = '你是一位辛苦批改作业的小学五年级数学老师。下面是一位学生写好的作业照片。\n\n'+
        '标准答案：\n'+std+'\n\n'+
        '请仔细看照片，找到每一题学生手写的答案，逐题与标准答案比对判断是否做对。\n要求：\n'+
        '- 数值答案允许等价写法（0.5=1/2、48平方厘米=48cm²）；\n'+
        '- 看不清或没写的题，is_correct=false，student_answer 填“未作答”；\n'+
        '- 每题匹配一个知识点。'+kpHint+'\n'+
        '严格只返回 JSON，不要任何解释：\n'+
        '{"results":[{"no":1,"student_answer":"学生手写的答案","is_correct":true,"analysis":"简短点评","knowledge_point":"知识点名"}]}';
      var messages = [{ role:'user', content:[
        { type:'image_url', image_url:{ url: dataUrl } },
        { type:'text', text: prompt }
      ]}];
      return callVLM(messages, 2000);
    }).then(function(text){
      var result = parseJson(text);
      return { results: result.results || [] };
    });
  }

  // ---- 本地规则判分（不需要 Key / 不花钱）----
  function normalizeNumber(s){
    s = String(s==null?'':s).trim().replace(/\s/g,'').replace(/，/g,',');
    s = s.replace(/。/g,'.').replace(/．/g,'.').replace(/×/g,'*').replace(/÷/g,'/').replace(/－/g,'-').replace(/—/g,'-');
    s = s.replace(/(平方厘米|平方米|cm²?|cm2|平方|厘米|米|千克|克|元|个|只)$/,'');
    var v = parseFloat(s);
    if(!isNaN(v) && isFinite(v) && s!=='' && /^[-+]?\d*\.?\d+$/.test(s)) return Math.round(v*1e6)/1e6;
    return s;
  }
  function judge(studentAnswer, standardAnswer, qType){
    var std = String(standardAnswer==null?'':standardAnswer).trim();
    var stu = String(studentAnswer==null?'':studentAnswer).trim();
    var ok=false, note='';
    if(qType==='choice'){
      var sm = std.toUpperCase().match(/[A-D]/), tm = stu.toUpperCase().match(/[A-D]/);
      ok = !!(sm && tm && sm[0]===tm[0]);
      note = ok ? '选项匹配' : ('标准='+std+' 学生='+stu);
    }else if(qType==='fill' || qType==='calc' || !qType){
      var accepted = std.split('|');
      for(var i=0;i<accepted.length;i++){
        var na = normalizeNumber(accepted[i].trim()), ns = normalizeNumber(stu);
        if(na===ns){ ok=true; note='答案匹配'; break; }
        if(typeof na==='number' && typeof ns==='number' && Math.abs(na-ns)<1e-6){ ok=true; note='数值等价'; break; }
        if(String(na)===String(ns)){ ok=true; note='文本匹配'; break; }
      }
      if(!ok) note = '标准='+std+' 学生='+stu;
    }else{
      note='主观题需老师复核';
    }
    return { is_correct: ok, ratio: ok?1:0, note: note };
  }

  var AI = {
    hasKey: hasKey, getKey: getKey, setKey: setKey,
    getCfg: getCfg, setCfg: setCfg, baseUrl: baseUrl, model: model,
    parseHomework: parseHomework, gradePage: gradePage, judge: judge,
    callVLM: callVLM
  };
  global.AI = AI;
})(window);
