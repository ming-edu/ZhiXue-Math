/* 智学数学 · 浏览器本地数据层
 * 所有业务数据存于 localStorage，每人独立、互不可见。
 * 首次访问自动注入演示数据作为引导；一键重置可清空为全空。
 */
(function (global) {
  'use strict';

  var KEY = 'zhixue_math_v1';
  var TABLES = ['teachers','classes','students','assignments','questions',
                'submissions','learning_records','variant_assignments'];
  var DEMO_URL = 'static/demo_data.json';
  var KG_URL = 'static/kg.json';

  var state = null;   // { version, initialized, demo:bool, tables:{...} }
  var kgCache = null;

  function nowISO(){ return new Date().toISOString(); }
  function clone(o){ return JSON.parse(JSON.stringify(o)); }

  var DATA_SCHEMA = 2;  // 数据结构版本；用于识别旧版残留的空壳数据

  function emptyState(){
    var tables = {};
    TABLES.forEach(function(t){ tables[t] = []; });
    return { version: 1, schema: DATA_SCHEMA, initialized: true, demo: false, tables: tables };
  }

  function load(){
    try{
      var raw = localStorage.getItem(KEY);
      if(raw){
        var s = JSON.parse(raw);
        if(s && s.tables){
          TABLES.forEach(function(t){ if(!s.tables[t]) s.tables[t] = []; });
          // 旧版（无 schema 标记）在 file:// 下 fetch 失败会写入空壳数据，
          // 这种残留会挡住演示数据注入。识别为「无标记且全空」则重新注入演示。
          // 用户主动「清空重置」写入的空数据带 schema 标记，不会被误判。
          if(s.schema !== DATA_SCHEMA){
            var any = TABLES.some(function(t){ return (s.tables[t]||[]).length > 0; });
            if(!any) return null;
          }
          return s;
        }
      }
    }catch(e){ console.warn('读取本地数据失败', e); }
    return null;
  }

  function persist(){
    try{
      localStorage.setItem(KEY, JSON.stringify(state));
      return true;
    }catch(e){
      console.error('本地存储写入失败（可能已满）', e);
      throw e;
    }
  }

  // 生成 8 位班级号（去除易混淆字符 0/O/1/I），保证在当前所有班级中唯一
  function genClassCode(){
    var chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    var existing = {};
    (state.tables.classes || []).forEach(function(c){ if(c.class_code) existing[c.class_code] = true; });
    var code;
    do{
      code = '';
      for(var i=0;i<8;i++) code += chars[Math.floor(Math.random()*chars.length)];
    }while(existing[code]);
    return code;
  }

  function nextId(table){
    var rows = state.tables[table] || [];
    var max = 0;
    rows.forEach(function(r){ if(r.id > max) max = r.id; });
    return max + 1;
  }

  // ===== 数据备份 / 跨设备迁移 =====
  var APP_ID = 'zhixue-math-backup';
  var BACKUP_FORMAT = 1;

  function statsOf(tables){
    tables = tables || {};
    return {
      classes: (tables.classes||[]).length,
      students: (tables.students||[]).length,
      assignments: (tables.assignments||[]).length,
      questions: (tables.questions||[]).length,
      submissions: (tables.submissions||[]).length,
      learning_records: (tables.learning_records||[]).length,
      variant_assignments: (tables.variant_assignments||[]).length
    };
  }

  function normalizeTables(raw){
    var t = {};
    TABLES.forEach(function(name){ t[name] = Array.isArray(raw[name]) ? clone(raw[name]) : []; });
    return t;
  }

  function parseBackup(text){
    var obj;
    try{ obj = JSON.parse(text); }
    catch(e){ throw new Error('文件不是有效的 JSON，请确认选的是本系统导出的备份文件'); }
    if(!obj || typeof obj !== 'object' || !obj.tables || typeof obj.tables !== 'object'){
      throw new Error('这不是智学数学的数据备份文件（缺少数据表）');
    }
    if(!TABLES.some(function(t){ return Array.isArray(obj.tables[t]); })){
      throw new Error('备份文件里没有可识别的数据表');
    }
    return obj;
  }

  function buildBackup(){
    if(!state) throw new Error('数据尚未加载完成，请稍候再试');
    return {
      app: APP_ID,
      format: BACKUP_FORMAT,
      exported_at: nowISO(),
      is_demo: !!state.demo,
      stats: statsOf(state.tables),
      tables: clone(state.tables)
    };
  }

  function downloadBackup(){
    var text = JSON.stringify(buildBackup());
    var blob = new Blob([text], {type:'application/json;charset=utf-8'});
    var url = URL.createObjectURL(blob);
    var d = new Date();
    function p(n){ return String(n).length<2 ? '0'+n : ''+n; }
    var stamp = ''+d.getFullYear()+p(d.getMonth()+1)+p(d.getDate())+'_'+p(d.getHours())+p(d.getMinutes());
    var a = document.createElement('a');
    a.href = url;
    a.download = '智学数学_数据备份_'+stamp+'.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function(){ URL.revokeObjectURL(url); }, 1500);
    return true;
  }

  function maxId(rows){
    var m = 0;
    (rows||[]).forEach(function(r){ var v=Number(r.id); if(v>m) m=v; });
    return m;
  }

  // 合并两批数据：以稳定标识去重，并重映射外键 id，避免不同设备 id 冲突导致关联错乱
  function mergeState(cur, inc){
    var out = { version:1, initialized:true, demo:false, tables:{} };
    TABLES.forEach(function(t){ out.tables[t] = clone(cur.tables[t]||[]); });
    var idMap = {};
    TABLES.forEach(function(t){ idMap[t] = {}; });
    var keys = {
      teachers: function(r){ return 'n:'+String(r.name||''); },
      classes: function(r){ return 'c:'+String(r.class_code||'').toUpperCase(); },
      students: function(r){ return 's:'+String(r.class_id)+':'+String(r.name||''); },
      assignments: function(r){ return 'a:'+String(r.class_id)+':'+String(r.title||'')+':'+String(r.created_at||''); },
      questions: function(r){ return 'q:'+String(r.assignment_id)+':'+String(r.sort_order)+':'+String(r.question_text||'').slice(0,40); },
      submissions: function(r){ return 'u:'+String(r.student_id)+':'+String(r.question_id); },
      learning_records: function(r){ return 'l:'+String(r.student_id)+':'+String(r.knowledge_point)+':'+String(r.timestamp||''); },
      variant_assignments: function(r){ return 'v:'+String(r.id); }
    };
    function remap(table, val){
      if(val===undefined || val===null || val==='') return val;
      var m = idMap[table] || {};
      return m[val] !== undefined ? m[val] : val;
    }
    function put(table, row, key){
      var arr = out.tables[table];
      var found = null;
      if(key){
        for(var i=0;i<arr.length;i++){
          if(keys[table] && keys[table](arr[i])===key){ found=arr[i]; break; }
        }
      }
      if(found){
        if(row.id !== undefined) idMap[table][row.id] = found.id;
        Object.keys(row).forEach(function(k){ if(k!=='id') found[k] = row[k]; });
        return found;
      }
      var newId = maxId(arr) + 1;
      var nr = clone(row);
      nr.id = newId;
      arr.push(nr);
      if(row.id !== undefined) idMap[table][row.id] = newId;
      return nr;
    }

    (inc.teachers||[]).forEach(function(r0){
      var r=clone(r0); r.teacher_id=remap('teachers', r.teacher_id); put('teachers', r, keys.teachers(r));
    });
    (inc.classes||[]).forEach(function(r0){
      var r=clone(r0); r.teacher_id=remap('teachers', r.teacher_id); put('classes', r, keys.classes(r));
    });
    (inc.students||[]).forEach(function(r0){
      var r=clone(r0); r.class_id=remap('classes', r.class_id); put('students', r, keys.students(r));
    });
    (inc.assignments||[]).forEach(function(r0){
      var r=clone(r0); r.class_id=remap('classes', r.class_id); r.teacher_id=remap('teachers', r.teacher_id);
      put('assignments', r, keys.assignments(r));
    });
    (inc.questions||[]).forEach(function(r0){
      var r=clone(r0); r.assignment_id=remap('assignments', r.assignment_id); put('questions', r, keys.questions(r));
    });
    (inc.submissions||[]).forEach(function(r0){
      var r=clone(r0); r.student_id=remap('students', r.student_id); r.question_id=remap('questions', r.question_id);
      put('submissions', r, keys.submissions(r));
    });
    (inc.learning_records||[]).forEach(function(r0){
      var r=clone(r0); r.student_id=remap('students', r.student_id); put('learning_records', r, keys.learning_records(r));
    });
    (inc.variant_assignments||[]).forEach(function(r0){
      var r=clone(r0); r.student_id=remap('students', r.student_id); put('variant_assignments', r, keys.variant_assignments(r));
    });
    return out;
  }

  var Store = {
    TABLES: TABLES,

    // 初始化：已初始化则读取；否则注入演示数据。返回 Promise
    init: function(forceDemo){
      var self = this;
      var existing = load();
      if(existing && !forceDemo){
        state = existing;
        return Promise.resolve(state);
      }
      // 首次访问或强制恢复演示数据。
      // 优先用内联数据（window.__DEMO_DATA__）：file:// 双击打开时 fetch 会被 CORS 拦截，
      // 而 <script> 标签加载不受限制，保证静态版本地直接可用。
      var inline = (typeof window !== 'undefined') ? window.__DEMO_DATA__ : null;
      if(inline){
        state = emptyState();
        TABLES.forEach(function(t){ state.tables[t] = clone(inline[t] || []); });
        state.demo = true;
        persist();
        return Promise.resolve(state);
      }
      // 兜底：网络环境用 fetch 拉取静态 JSON
      return fetch(DEMO_URL).then(function(r){ return r.json(); }).then(function(demo){
        state = emptyState();
        TABLES.forEach(function(t){ state.tables[t] = clone(demo[t] || []); });
        state.demo = true;
        persist();
        return state;
      }).catch(function(e){
        console.error('注入演示数据失败，改用空数据', e);
        state = emptyState();
        persist();
        return state;
      });
    },

    // 一键重置为全空（用户明确选择）
    resetAll: function(){
      state = emptyState();
      persist();
      return state;
    },

    // 恢复演示数据（可选补救）
    restoreDemo: function(){
      return this.init(true);
    },

    isDemo: function(){ return state && state.demo; },

    // ---- 通用 CRUD ----
    all: function(table){ return clone(state.tables[table] || []); },
    count: function(table){ return (state.tables[table] || []).length; },
    get: function(table, id){
      id = Number(id);
      return clone((state.tables[table] || []).find(function(r){ return r.id === id; }) || null);
    },
    where: function(table, fn){ return clone((state.tables[table] || []).filter(fn)); },

    insert: function(table, obj){
      var row = clone(obj);
      if(!row.id) row.id = nextId(table);
      if(!row.created_at && TABLES.indexOf(table) >= 0) row.created_at = nowISO();
      state.tables[table].push(row);
      persist();
      return clone(row);
    },

    update: function(table, id, patch){
      id = Number(id);
      var row = (state.tables[table] || []).find(function(r){ return r.id === id; });
      if(!row) return null;
      Object.keys(patch).forEach(function(k){ row[k] = patch[k]; });
      persist();
      return clone(row);
    },

    remove: function(table, id){
      id = Number(id);
      var arr = state.tables[table] || [];
      var idx = arr.findIndex(function(r){ return r.id === id; });
      if(idx >= 0){ arr.splice(idx,1); persist(); return true; }
      return false;
    },

    removeWhere: function(table, fn){
      var arr = state.tables[table] || [];
      var before = arr.length;
      state.tables[table] = arr.filter(function(r){ return !fn(r); });
      if(state.tables[table].length !== before) persist();
      return before - state.tables[table].length;
    },

    // ---- 班级与学生 ----
    genClassCode: genClassCode,

    createClass: function(name, teacherName, grade, semester){
      var code = genClassCode();
      var row = { name: name };
      if(teacherName !== undefined) row.teacher_name = String(teacherName||'').trim();
      row.grade = grade || '五年级';
      row.semester = semester || '上册';
      row.teacher_id = 1;
      row.class_code = code;
      row.created_at = nowISO();
      return this.insert('classes', row);
    },

    // 更新班级的年级/学期/老师（切换教材不影响任何学生与历史数据）
    setClassGrade: function(class_id, grade, semester){
      return this.update('classes', Number(class_id), {
        grade: grade || '五年级', semester: semester || '上册'
      });
    },
    setClassTeacher: function(class_id, teacherName){
      return this.update('classes', Number(class_id), { teacher_name: String(teacherName||'').trim() });
    },

    // 批量导入学生：names 为字符串数组，去重、过滤空
    addStudents: function(class_id, names){
      var added = [];
      var existing = new Set((state.tables.students||[]).filter(function(s){return s.class_id===Number(class_id);}).map(function(s){return s.name;}));
      names.forEach(function(n){
        n = String(n||'').trim();
        if(!n || existing.has(n)) return;
        existing.add(n);
        var no = (state.tables.students||[]).filter(function(s){return s.class_id===Number(class_id);}).length + 1;
        added.push(Store.insert('students', { name: n, class_id: Number(class_id), student_no: no }));
      });
      return added;
    },

    deleteClass: function(class_id){
      class_id = Number(class_id);
      var stuIds = (state.tables.students||[]).filter(function(s){return s.class_id===class_id;}).map(function(s){return s.id;});
      var aidIds = (state.tables.assignments||[]).filter(function(a){return a.class_id===class_id;}).map(function(a){return a.id;});
      var qIds = (state.tables.questions||[]).filter(function(q){return aidIds.indexOf(q.assignment_id)>=0;}).map(function(q){return q.id;});
      this.removeWhere('submissions', function(r){ return stuIds.indexOf(r.student_id)>=0 || qIds.indexOf(r.question_id)>=0; });
      this.removeWhere('learning_records', function(r){ return stuIds.indexOf(r.student_id)>=0; });
      this.removeWhere('variant_assignments', function(r){ return stuIds.indexOf(r.student_id)>=0; });
      this.removeWhere('questions', function(q){ return aidIds.indexOf(q.assignment_id)>=0; });
      this.removeWhere('assignments', function(a){ return a.class_id===class_id; });
      this.removeWhere('students', function(s){ return s.class_id===class_id; });
      this.remove('classes', class_id);
    },

    // ---- 知识图谱（只读公共数据）----
    loadKG: function(){
      if(kgCache) return Promise.resolve(kgCache);
      // 优先用内联知识图谱（file:// 下 fetch 受限）
      var inline = (typeof window !== 'undefined') ? window.__KG_DATA__ : null;
      if(inline){ kgCache = inline; return Promise.resolve(inline); }
      return fetch(KG_URL).then(function(r){ return r.json(); }).then(function(d){ kgCache = d; return d; });
    },
    kg: function(){ return kgCache; },

    // 班级概览（前端版）
    classOverview: function(class_id){
      class_id = Number(class_id);
      var students = (state.tables.students||[]).filter(function(s){return s.class_id===class_id;});
      var stuIds = {}; students.forEach(function(s){ stuIds[s.id] = true; });
      var recs = (state.tables.learning_records||[]).filter(function(r){ return stuIds[r.student_id]; });
      var total = students.length;
      if(!total) return { student_count: 0, avg_accuracy: 0, total_records: 0, ranking: [], weak_points: [] };
      var corr = recs.reduce(function(a,r){ return a + (r.correct?1:0); }, 0);
      var ranking = students.map(function(s){
        var sr = recs.filter(function(r){return r.student_id===s.id;});
        var c = sr.reduce(function(a,r){return a+(r.correct?1:0);},0);
        return { id:s.id, name:s.name, accuracy: sr.length? +(c/sr.length).toFixed(3):0, point_count: sr.length };
      }).filter(function(x){return x.point_count>0;});
      ranking.sort(function(a,b){ return b.accuracy-a.accuracy; });
      // 薄弱点 top5
      var byKp = {};
      recs.forEach(function(r){
        if(!byKp[r.knowledge_point]) byKp[r.knowledge_point] = {total:0,correct:0,score:0};
        byKp[r.knowledge_point].total++;
        byKp[r.knowledge_point].correct += r.correct?1:0;
        byKp[r.knowledge_point].score += (r.score||0);
      });
      var weak = Object.keys(byKp).map(function(k){
        var v = byKp[k];
        return { knowledge_point:k, total:v.total, correct:v.correct,
                 accuracy: v.total? +(v.correct/v.total).toFixed(3):0,
                 avg_score: v.total? +(v.score/v.total).toFixed(3):0 };
      }).sort(function(a,b){ return a.accuracy-b.accuracy; }).slice(0,5);
      return {
        student_count: total,
        avg_accuracy: recs.length? +(corr/recs.length).toFixed(3):0,
        total_records: recs.length,
        ranking: ranking,
        weak_points: weak
      };
    },

    // ---- 数据备份与跨设备迁移 ----
    getStats: function(){ return statsOf(state ? state.tables : {}); },

    // 生成备份对象（不下载），便于预览与测试
    buildBackup: buildBackup,

    // 下载备份文件到本机（文件名含日期时间）
    downloadBackup: downloadBackup,

    // 读取并校验备份，返回展示用摘要（不改动当前数据）
    getBackupSummary: function(text){
      var obj = parseBackup(text);
      var tables = normalizeTables(obj.tables);
      return {
        app: obj.app || '',
        exported_at: obj.exported_at || null,
        is_demo: !!obj.is_demo,
        stats: (obj.stats && typeof obj.stats === 'object') ? obj.stats : statsOf(tables),
        tables: tables
      };
    },

    // 导入备份：mode='replace' 覆盖 | 'merge' 合并
    importData: function(text, mode){
      var obj = parseBackup(text);
      var incoming = normalizeTables(obj.tables);
      if(mode === 'merge'){
        state = mergeState(state || emptyState(), incoming);
      }else{
        state = { version:1, schema: DATA_SCHEMA, initialized:true, demo: !!obj.is_demo, tables: incoming };
      }
      persist();
      return { mode: mode, stats: statsOf(state.tables) };
    },

    // 调试用：导出当前数据原始 JSON（不含元数据）
    exportData: function(){ return JSON.stringify(state, null, 2); }
  };

  global.Store = Store;
})(window);
