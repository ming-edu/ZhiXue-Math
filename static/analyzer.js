/* 智学数学 · 前端学情分析引擎（从 analyzer.py 移植）
 * 从 Store 读取本地数据，计算掌握度/薄弱点/素养诊断/专题/变式题。
 */
(function (global) {
  'use strict';

  function round(x, n){ var p = Math.pow(10, n||0); return Math.round(x*p)/p; }

  var Analyzer = {
    _kgMap: null,
    _kg: null,

    _initKG: function(){
      if(this._kg) return;
      this._kg = Store.kg();
      this._kgMap = {};
      (this._kg.knowledge_points || []).forEach(function(k){ Analyzer._kgMap[k.name] = k; });
    },

    masteryByStudent: function(sid){
      sid = Number(sid);
      var recs = Store.where('learning_records', function(r){ return r.student_id===sid; });
      var by = {};
      recs.forEach(function(r){
        if(!by[r.knowledge_point]) by[r.knowledge_point] = {total:0,correct:0,score:0};
        by[r.knowledge_point].total++;
        by[r.knowledge_point].correct += r.correct?1:0;
        by[r.knowledge_point].score += (r.score||0);
      });
      var out = {};
      Object.keys(by).forEach(function(k){
        var v = by[k];
        out[k] = { total:v.total, correct:v.correct,
                   accuracy: v.total? round(v.correct/v.total,3):0,
                   avg_score: v.total? round(v.score/v.total,3):0 };
      });
      return out;
    },

    masteryByClass: function(cid, topN){
      cid = Number(cid);
      var stus = Store.where('students', function(s){ return s.class_id===cid; });
      var ids = {}; stus.forEach(function(s){ ids[s.id]=true; });
      var recs = Store.where('learning_records', function(r){ return ids[r.student_id]; });
      var by = {};
      recs.forEach(function(r){
        if(!by[r.knowledge_point]) by[r.knowledge_point] = {total:0,correct:0,score:0};
        by[r.knowledge_point].total++;
        by[r.knowledge_point].correct += r.correct?1:0;
        by[r.knowledge_point].score += (r.score||0);
      });
      var out = Object.keys(by).map(function(k){
        var v = by[k];
        return { knowledge_point:k, total:v.total, correct:v.correct,
                 accuracy: v.total? round(v.correct/v.total,3):0,
                 avg_score: v.total? round(v.score/v.total,3):0 };
      });
      out.sort(function(a,b){ return a.accuracy-b.accuracy; });
      return topN ? out.slice(0,topN) : out;
    },

    weakPoints: function(opt){
      opt = opt || {};
      var items = [];
      if(opt.student_id){
        var m = this.masteryByStudent(opt.student_id);
        Object.keys(m).forEach(function(k){ items.push(Object.assign({knowledge_point:k}, m[k])); });
      } else if(opt.class_id){
        items = this.masteryByClass(opt.class_id);
      }
      var threshold = opt.threshold!=null?opt.threshold:0.6;
      var minAttempts = opt.min_attempts!=null?opt.min_attempts:2;
      var weak = items.filter(function(x){ return x.accuracy<threshold && x.total>=minAttempts; });
      weak.sort(function(a,b){ return (a.accuracy-b.accuracy) || (b.total-a.total); });
      return weak;
    },

    competencyDiagnosis: function(weakList){
      this._initKG();
      var kgMap = this._kgMap;
      var core = this._kg.core_competencies;
      var domains = this._kg.competency_domain;
      var score = {}, hit = {}, evidence = {};
      weakList.forEach(function(wp){
        var kp = kgMap[wp.knowledge_point];
        if(!kp) return;
        var severity = 1 - wp.accuracy;
        (kp.competencies||[]).forEach(function(c){
          score[c] = (score[c]||0) + severity;
          hit[c] = (hit[c]||0) + 1;
          if(!evidence[c]) evidence[c] = [];
          evidence[c].push({ point:wp.knowledge_point, accuracy:wp.accuracy, error_pattern:kp.error_pattern });
        });
      });
      var diag = Object.keys(core).map(function(comp){
        var raw = score[comp]||0;
        var level = Math.max(0, Math.min(100, Math.round(100 - raw*25)));
        return { competency:comp, domain:domains[comp], level:level,
                 hits:hit[comp]||0, evidence:evidence[comp]||[], description:core[comp] };
      });
      diag.sort(function(a,b){ return a.level-b.level; });
      return diag;
    },

    genVariant: function(kpName){
      this._initKG();
      var tpls = this._kg.variant_templates;
      var generic = this._kg.generic_variant;
      var tpl = tpls[kpName] || generic;
      var templates = tpl.templates || [];
      if(!templates.length) templates = ['请说一说关于{kp}的一个例子，并说明理由。'];
      var chosen = templates[Math.floor(Math.random()*templates.length)];
      function ri(a,b){ return a + Math.floor(Math.random()*(b-a+1)); }
      function rf(a,b,d){ return round(a + Math.random()*(b-a), d||1); }
      var answer = '（开放题，老师复核）';
      var context = '';
      var hasNum = /\{[abcnmk]\}/.test(chosen);
      if(hasNum){
        if(kpName==='小数加减法'){
          var a=rf(1.1,9.9,1), b=rf(1.1,9.9,1);
          if(chosen.indexOf('-')>=0 && b>a){ var t=a;a=b;b=t; }
          answer = round(chosen.indexOf('+')>=0?a+b:a-b,1);
          chosen = chosen.replace(/\{a\}/g,a).replace(/\{b\}/g,b);
        } else if(kpName.indexOf('小数乘小数')>=0 || kpName.indexOf('小数乘整数')>=0 || kpName.indexOf('小数乘法简算')>=0){
          var a2=rf(1.2,9.9,1), b2=(kpName.indexOf('小数乘小数')>=0)?rf(1.2,5.9,1):ri(2,9);
          answer = round(a2*b2,2);
          chosen = chosen.replace(/\{a\}/g,a2).replace(/\{b\}/g,b2);
        } else if(kpName.indexOf('三角形的面积')>=0){
          var a3=ri(4,15), b3=ri(3,12); answer=round(a3*b3/2,2);
          chosen = chosen.replace(/\{a\}/g,a3).replace(/\{b\}/g,b3);
        } else if(kpName.indexOf('平行四边形的面积')>=0){
          var a4=ri(4,15), b4=ri(3,12); answer=a4*b4;
          chosen = chosen.replace(/\{a\}/g,a4).replace(/\{b\}/g,b4);
        } else if(kpName.indexOf('梯形')>=0){
          var a5=ri(3,9), b5=ri(10,18), c5=ri(3,10); answer=round((a5+b5)*c5/2,2);
          chosen = chosen.replace(/\{a\}/g,a5).replace(/\{b\}/g,b5).replace(/\{c\}/g,c5);
        } else if(kpName.indexOf('3的倍数')>=0){
          var n6=ri(100,999); answer = n6%3===0?'是':'不是';
          chosen = chosen.replace(/\{n\}/g,n6);
        } else if(kpName.indexOf('倍数与因数')>=0){
          var n7=ri(12,36);
          answer = chosen.indexOf('倍数')>=0?'1、它本身':Array.from({length:n7},function(_,i){return i+1;}).filter(function(i){return n7%i===0;}).join('、');
          chosen = chosen.replace(/\{n\}/g,n7);
        } else if(kpName.indexOf('用字母表示')>=0){
          var n8=ri(3,12); answer = chosen.indexOf('多')>=0?('a+'+n8):(n8+'b');
          chosen = chosen.replace(/\{n\}/g,n8);
        } else if(kpName.indexOf('质数')>=0 || kpName.indexOf('合数')>=0){
          var primes=[2,3,5,7,11,13,17,19];
          function isP(x){ if(x<2)return false; for(var d=2;d*d<=x;d++) if(x%d===0)return false; return true; }
          var p=primes[Math.floor(Math.random()*primes.length)];
          var comp=[21,25,27,33,15,18][Math.floor(Math.random()*6)];
          var c9=[4,6,8,12,20][Math.floor(Math.random()*5)];
          if(chosen.indexOf('{n}')>=0 && chosen.indexOf('{m}')<0){
            var target = Math.random()<0.5?p:comp;
            answer = isP(target)?'质数':'合数';
            chosen = chosen.replace(/\{n\}/g,target);
          } else {
            answer = [p,comp,c9].filter(isP).join('、');
            chosen = chosen.replace(/\{n\}/g,p).replace(/\{m\}/g,comp).replace(/\{k\}/g,c9);
          }
        } else if(kpName.indexOf('积的近似数')>=0){
          var a10=rf(1.2,9.9,2), b10=rf(1.1,5.9,2); answer=round(a10*b10,1);
          chosen = chosen.replace(/\{a\}/g,a10).replace(/\{b\}/g,b10);
        } else {
          var a11=rf(1,10,1), b11=rf(1,10,1); answer=round(a11+b11,2);
          chosen = chosen.replace(/\{a\}/g,a11).replace(/\{b\}/g,b11);
        }
      } else {
        chosen = chosen.replace(/\{kp\}/g,kpName).replace(/\{context\}/g,context);
      }
      return {
        knowledge_point:kpName, question_text:chosen, answer:String(answer),
        analysis:tpl.analysis||'', created_at:nowISO()
      };
      function nowISO(){ return new Date().toISOString(); }
    },

    generateVariantSet: function(opt, n){
      opt = opt||{}; n = n||5;
      var weak = this.weakPoints(opt);
      if(!weak.length) return [];
      var out = [];
      for(var i=0;i<n;i++){
        var wp = weak[i%weak.length];
        var ex = this.genVariant(wp.knowledge_point);
        ex.source_weakness = wp.knowledge_point;
        ex.source_accuracy = wp.accuracy;
        out.push(ex);
        if(opt.student_id) Store.insert('variant_assignments', {
          student_id:Number(opt.student_id), knowledge_point:ex.knowledge_point,
          question_text:ex.question_text, answer:ex.answer, analysis:ex.analysis,
          is_done:0, is_correct:0, created_at:ex.created_at
        });
      }
      return out;
    },

    topicRecommendations: function(opt){
      this._initKG();
      var kgMap = this._kgMap;
      var weak = this.weakPoints(opt);
      if(!weak.length) return [];
      var groups = {};
      weak.forEach(function(wp){
        var kp = kgMap[wp.knowledge_point];
        if(kp){ if(!groups[kp.domain]) groups[kp.domain]=[]; groups[kp.domain].push(wp); }
      });
      var self = this;
      var topics = Object.keys(groups).map(function(domain){
        var pts = groups[domain].slice().sort(function(a,b){return a.accuracy-b.accuracy;});
        var avg = round(pts.reduce(function(a,p){return a+p.accuracy;},0)/pts.length,3);
        var names = pts.map(function(p){return p.knowledge_point;});
        var comps = [];
        pts.forEach(function(p){ var kp=kgMap[p.knowledge_point]; if(kp) (kp.competencies||[]).forEach(function(c){ if(comps.indexOf(c)<0) comps.push(c); }); });
        return { domain:domain, weak_count:pts.length, avg_accuracy:avg, points:names,
                 competencies:comps.sort(), title:domain+'专题突破',
                 suggestion:self._suggestion(domain, names) };
      });
      topics.sort(function(a,b){ return a.avg_accuracy-b.avg_accuracy; });
      return topics;
    },

    _suggestion: function(domain, points){
      var map = {
        '数与代数':'建议安排「算理理解 + 运算技能」双线训练：先通过实例讲清算理，再设计分层计算练习，重点纠正小数点位置和运算顺序类错误。',
        '图形与几何':'建议安排「操作感知 + 转化思想」专题：借助剪纸、割补、拼摆等活动建立空间表象，强化底与高的对应关系和公式推导过程。',
        '统计与概率':'建议安排「数据感悟 + 随机现象体验」活动：通过摸球、掷骰等实验建立可能性大小与数量的关系，用真实数据支撑判断。',
        '综合与实践':'建议安排「问题解决策略」专题：训练列表、假设、画图等策略的灵活选择，鼓励一题多解，发展模型意识与创新意识。'
      };
      var base = map[domain] || '针对薄弱知识点设计分层练习与变式训练。';
      return base + ' 本专题聚焦：' + points.slice(0,5).join('、') + '。';
    }
  };

  global.Analyzer = Analyzer;
})(window);
