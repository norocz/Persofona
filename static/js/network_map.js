/* PersonDB — Full-page Network Map with Layout Modes
   Modes: force, tree (family), radial, clusters */

(function() {
  'use strict';

  const canvas = document.getElementById('fullmap');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  let nodes = [], edges = [], groups = [], tags = [];
  let nodeMap = {};
  let showLabels = true, physicsRunning = true;
  let currentLayout = 'force';
  let scale = 1, offsetX = 0, offsetY = 0;
  let dragNode = null, isPanning = false, panStart = {x:0,y:0};
  let hoveredNode = null;
  let W, H;

  const FAMILY_TYPES = new Set(['parent','child','grandparent','grandchild','sibling','spouse','partner','uncle_aunt','cousin']);
  const REL_COLORS = {
    parent:'#4fc3f7',child:'#4fc3f7',sibling:'#81c784',spouse:'#f06292',partner:'#f06292',
    friend:'#00ff41',bestfriend:'#ffeb3b',colleague:'#ff9800',boss:'#ff5722',enemy:'#f44336',
    acquaintance:'#78909c',other:'#607d8b',grandparent:'#4fc3f7',grandchild:'#4fc3f7',
    uncle_aunt:'#4fc3f7',cousin:'#81c784',subordinate:'#ff9800',classmate:'#9c27b0',
    neighbor:'#8bc34a',mentor:'#00bcd4',mentee:'#00bcd4'
  };
  const REL_LABELS = {
    parent:'Rodič',child:'Dítě',sibling:'Sourozenec',spouse:'Manžel/ka',partner:'Partner/ka',
    friend:'Přítel',bestfriend:'Nejlepší přítel',colleague:'Kolega',boss:'Nadřízený',
    subordinate:'Podřízený',classmate:'Spolužák',neighbor:'Soused',acquaintance:'Známý',
    enemy:'Nepřítel',mentor:'Mentor',mentee:'Mentee',other:'Jiný',
    grandparent:'Prarodič',grandchild:'Vnuk/vnučka',uncle_aunt:'Strýc/teta',cousin:'Bratranec'
  };

  function resize() {
    const r = canvas.parentElement.getBoundingClientRect();
    W = canvas.width = r.width; H = canvas.height = r.height;
  }

  // ==================== Data Loading ====================
  function loadData() {
    fetch(GRAPH_DATA_URL).then(r=>r.json()).then(data => {
      groups = data.groups || []; tags = data.tags || [];
      const count = data.nodes.length;
      nodes = data.nodes.map((n,i) => ({
        ...n, x: W/2 + (Math.random()-.5)*W*.6, y: H/2 + (Math.random()-.5)*H*.6,
        vx:0, vy:0, radius: n.fav ? 24 : 18, visible: true, generation: null
      }));
      nodeMap = {};
      nodes.forEach(n => nodeMap[n.id] = n);
      edges = data.edges.filter(e => nodeMap[e.from] && nodeMap[e.to]).map(e => ({
        ...e, a: nodeMap[e.from], b: nodeMap[e.to]
      }));
      applyLayout(currentLayout);
      buildLegend(); buildFilters(); tick();
    }).catch(() => {
      ctx.fillStyle='#4a5f72'; ctx.font='14px JetBrains Mono'; ctx.textAlign='center';
      ctx.fillText('Chyba při načítání dat', W/2, H/2);
    });
  }

  // ==================== Layout Algorithms ====================

  function applyLayout(mode) {
    currentLayout = mode;
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));

    switch(mode) {
      case 'tree': layoutTree(); physicsRunning = false; break;
      case 'radial': layoutRadial(); physicsRunning = false; break;
      case 'clusters': layoutClusters(); physicsRunning = true; break;
      default: layoutForce(); physicsRunning = true; break;
    }
    updatePhysicsBtn();
  }

  function updatePhysicsBtn() {
    const btn = document.getElementById('btn-physics');
    if (btn) { btn.textContent = physicsRunning ? '▶' : '⏸'; btn.style.color = physicsRunning ? 'var(--green)' : 'var(--amber)'; }
  }

  // --- Force layout (initial scatter) ---
  function layoutForce() {
    const count = nodes.length;
    nodes.forEach((n, i) => {
      const angle = (2*Math.PI*i)/Math.max(count,1);
      const r = Math.min(W,H)*0.35;
      n.x = W/2 + r*Math.cos(angle) + (Math.random()-.5)*60;
      n.y = H/2 + r*Math.sin(angle) + (Math.random()-.5)*60;
      n.vx = 0; n.vy = 0;
    });
  }

  // --- Tree layout (family hierarchy) ---
  function layoutTree() {
    // Build parent→child adjacency from edge types
    const childrenOf = {}; // parentId → [childIds]
    const hasParent = new Set();

    edges.forEach(e => {
      // parent→child: person_from is parent of person_to
      if (e.type === 'parent') {
        if (!childrenOf[e.from]) childrenOf[e.from] = [];
        childrenOf[e.from].push(e.to);
        hasParent.add(e.to);
      }
      if (e.type === 'child') {
        if (!childrenOf[e.to]) childrenOf[e.to] = [];
        childrenOf[e.to].push(e.from);
        hasParent.add(e.from);
      }
    });

    // Find roots (no parents)
    const roots = nodes.filter(n => n.visible && !hasParent.has(n.id));
    // If no family structure, fall back to all nodes as roots
    const effectiveRoots = roots.length ? roots : nodes.filter(n => n.visible);

    // BFS to assign generations
    const visited = new Set();
    const genMap = {}; // id → generation
    const queue = [];

    effectiveRoots.forEach(n => { queue.push({id:n.id, gen:0}); visited.add(n.id); genMap[n.id]=0; });

    while (queue.length) {
      const {id, gen} = queue.shift();
      const children = childrenOf[id] || [];
      children.forEach(cid => {
        if (!visited.has(cid)) {
          visited.add(cid); genMap[cid] = gen+1;
          queue.push({id:cid, gen:gen+1});
        }
      });
    }

    // Assign gen 0 to unvisited
    nodes.forEach(n => { if (genMap[n.id] === undefined) genMap[n.id] = 0; });

    // Group by generation
    const generations = {};
    nodes.filter(n=>n.visible).forEach(n => {
      const g = genMap[n.id];
      if (!generations[g]) generations[g] = [];
      generations[g].push(n);
    });

    // Position: top to bottom, evenly spaced
    const genKeys = Object.keys(generations).map(Number).sort((a,b)=>a-b);
    const genCount = genKeys.length || 1;
    const vertSpacing = H / (genCount + 1);

    genKeys.forEach((gen, gi) => {
      const row = generations[gen];
      const horizSpacing = W / (row.length + 1);
      row.forEach((n, ni) => {
        n.x = horizSpacing * (ni + 1);
        n.y = vertSpacing * (gi + 1);
        n.vx = 0; n.vy = 0;
      });
    });

    // Also link spouses side-by-side
    edges.forEach(e => {
      if (e.type === 'spouse' || e.type === 'partner') {
        const a = nodeMap[e.from], b = nodeMap[e.to];
        if (a && b && Math.abs(a.y - b.y) < 5) {
          // Already same row, nudge together
          const mx = (a.x + b.x) / 2;
          a.x = mx - 30; b.x = mx + 30;
        }
      }
    });
  }

  // --- Radial layout (most connected at center) ---
  function layoutRadial() {
    // Count connections
    const connCount = {};
    nodes.forEach(n => connCount[n.id] = 0);
    edges.forEach(e => {
      if (nodeMap[e.from]) connCount[e.from] = (connCount[e.from]||0)+1;
      if (nodeMap[e.to]) connCount[e.to] = (connCount[e.to]||0)+1;
    });

    // Sort by connection count descending
    const sorted = nodes.filter(n=>n.visible).slice().sort((a,b) => (connCount[b.id]||0) - (connCount[a.id]||0));

    // Assign rings using BFS from most connected
    const center = sorted[0];
    if (!center) return;

    center.x = W/2; center.y = H/2; center.vx=0; center.vy=0;

    const visited = new Set([center.id]);
    const queue = [{node:center, ring:0}];
    const rings = {0: [center]};

    // BFS from center
    while (queue.length) {
      const {node, ring} = queue.shift();
      const neighbors = [];
      edges.forEach(e => {
        if (e.from === node.id && nodeMap[e.to] && !visited.has(e.to)) neighbors.push(e.to);
        if (e.to === node.id && nodeMap[e.from] && !visited.has(e.from)) neighbors.push(e.from);
      });
      neighbors.forEach(nid => {
        visited.add(nid);
        const r = ring + 1;
        if (!rings[r]) rings[r] = [];
        rings[r].push(nodeMap[nid]);
        queue.push({node: nodeMap[nid], ring: r});
      });
    }

    // Place unvisited in outermost ring
    const maxRing = Math.max(...Object.keys(rings).map(Number));
    nodes.filter(n => n.visible && !visited.has(n.id)).forEach(n => {
      const r = maxRing + 1;
      if (!rings[r]) rings[r] = [];
      rings[r].push(n);
    });

    // Position each ring concentrically
    const ringKeys = Object.keys(rings).map(Number).sort((a,b)=>a-b);
    const maxR = Math.min(W,H) * 0.42;
    const ringStep = maxR / Math.max(ringKeys.length, 1);

    ringKeys.forEach(ri => {
      const ring = rings[ri];
      const radius = ri === 0 ? 0 : ringStep * ri;
      ring.forEach((n, ni) => {
        if (ri === 0) { n.x = W/2; n.y = H/2; }
        else {
          const angle = (2*Math.PI*ni)/ring.length - Math.PI/2;
          n.x = W/2 + radius * Math.cos(angle);
          n.y = H/2 + radius * Math.sin(angle);
        }
        n.vx=0; n.vy=0;
      });
    });
  }

  // --- Cluster layout (group-based) ---
  function layoutClusters() {
    if (!groups.length) { layoutForce(); return; }

    const groupMap = {};
    groups.forEach((g, i) => {
      const angle = (2*Math.PI*i)/groups.length;
      const r = Math.min(W,H)*0.28;
      groupMap[g.id] = { cx: W/2+r*Math.cos(angle), cy: H/2+r*Math.sin(angle), ...g };
    });

    nodes.forEach(n => {
      if (n.group_ids && n.group_ids.length > 0) {
        let cx=0, cy=0, cnt=0;
        n.group_ids.forEach(gid => {
          const gp = groupMap[gid];
          if (gp) { cx+=gp.cx; cy+=gp.cy; cnt++; }
        });
        if (cnt) { n.x=cx/cnt+(Math.random()-.5)*80; n.y=cy/cnt+(Math.random()-.5)*80; }
      } else {
        n.x = W/2+(Math.random()-.5)*100;
        n.y = H/2+(Math.random()-.5)*100;
      }
      n.vx=0; n.vy=0;
    });
  }

  // ==================== Physics Simulation ====================
  function simulate() {
    if (!physicsRunning) return;
    const repulsion = 4500, edgeK = 0.006, damping = 0.88;

    // Group cluster gravity for cluster mode
    const groupCenters = {};
    if (currentLayout === 'clusters' && groups.length) {
      groups.forEach((g,i) => {
        const angle=(2*Math.PI*i)/groups.length;
        const r=Math.min(W,H)*0.28;
        groupCenters[g.id]={cx:W/2+r*Math.cos(angle),cy:H/2+r*Math.sin(angle)};
      });
    }

    for (let i=0;i<nodes.length;i++) {
      if (!nodes[i].visible) continue;
      for (let j=i+1;j<nodes.length;j++) {
        if (!nodes[j].visible) continue;
        const dx=nodes[j].x-nodes[i].x, dy=nodes[j].y-nodes[i].y;
        const dist=Math.sqrt(dx*dx+dy*dy)||1;
        const f=repulsion/(dist*dist);
        const fx=(dx/dist)*f, fy=(dy/dist)*f;
        nodes[i].vx-=fx; nodes[i].vy-=fy;
        nodes[j].vx+=fx; nodes[j].vy+=fy;
      }
    }

    edges.forEach(e => {
      if (!e.a.visible||!e.b.visible) return;
      const dx=e.b.x-e.a.x, dy=e.b.y-e.a.y;
      const dist=Math.sqrt(dx*dx+dy*dy)||1;
      const f=(dist-140)*edgeK;
      const fx=(dx/dist)*f, fy=(dy/dist)*f;
      e.a.vx+=fx; e.a.vy+=fy; e.b.vx-=fx; e.b.vy-=fy;
    });

    if (currentLayout === 'clusters') {
      nodes.forEach(n => {
        if (!n.visible||!n.group_ids) return;
        n.group_ids.forEach(gid => {
          const gc=groupCenters[gid];
          if (gc) { n.vx+=(gc.cx-n.x)*0.003; n.vy+=(gc.cy-n.y)*0.003; }
        });
      });
    }

    nodes.forEach(n => {
      if (!n.visible) return;
      n.vx+=(W/2-n.x)*0.0004; n.vy+=(H/2-n.y)*0.0004;
      n.vx*=damping; n.vy*=damping;
      if (dragNode!==n) { n.x+=n.vx; n.y+=n.vy; }
      n.x=Math.max(40,Math.min(W-40,n.x));
      n.y=Math.max(40,Math.min(H-40,n.y));
    });
  }

  // ==================== Draw ====================
  function draw() {
    ctx.save();
    ctx.clearRect(0,0,W,H);
    ctx.translate(offsetX,offsetY);
    ctx.scale(scale,scale);

    // Draw group hulls in cluster mode
    if (currentLayout === 'clusters' && groups.length) {
      groups.forEach(g => {
        const members = nodes.filter(n=>n.visible&&n.group_ids&&n.group_ids.includes(g.id));
        if (members.length<2) return;
        let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
        members.forEach(n=>{if(n.x<minX)minX=n.x;if(n.y<minY)minY=n.y;if(n.x>maxX)maxX=n.x;if(n.y>maxY)maxY=n.y;});
        const pad=50,cx=(minX+maxX)/2,cy=(minY+maxY)/2;
        const rx=(maxX-minX)/2+pad,ry=(maxY-minY)/2+pad;
        ctx.beginPath();ctx.ellipse(cx,cy,Math.max(rx,60),Math.max(ry,50),0,0,Math.PI*2);
        ctx.fillStyle=(g.color||'#00ff41')+'0a';ctx.fill();
        ctx.strokeStyle=(g.color||'#00ff41')+'30';ctx.lineWidth=1.5;
        ctx.setLineDash([6,4]);ctx.stroke();ctx.setLineDash([]);
        if (showLabels) {
          ctx.fillStyle=(g.color||'#00ff41')+'80';
          ctx.font='bold 11px IBM Plex Sans';ctx.textAlign='center';
          ctx.fillText(g.name.toUpperCase(),cx,minY-pad+12);
        }
      });
    }

    // Draw generation lines in tree mode
    if (currentLayout === 'tree') {
      const yValues = new Set();
      nodes.filter(n=>n.visible).forEach(n=>yValues.add(Math.round(n.y)));
      // Group nearby y values
      const sortedY = [...yValues].sort((a,b)=>a-b);
      const genYs = [];
      sortedY.forEach(y => {
        if (!genYs.length || y - genYs[genYs.length-1] > 30) genYs.push(y);
      });
      genYs.forEach((y,i) => {
        ctx.strokeStyle = '#00ff4110'; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke();
        if (showLabels) {
          ctx.fillStyle = '#00ff4130'; ctx.font = '10px JetBrains Mono'; ctx.textAlign = 'left';
          ctx.fillText(`Gen ${i}`, 10, y-6);
        }
      });
    }

    // Draw radial rings
    if (currentLayout === 'radial') {
      const maxR = Math.min(W,H)*0.42;
      for (let i=1;i<=5;i++) {
        ctx.beginPath();ctx.arc(W/2,H/2,maxR*i/5,0,Math.PI*2);
        ctx.strokeStyle='#00ff4108';ctx.lineWidth=1;ctx.stroke();
      }
    }

    // Edges
    edges.forEach(e => {
      if (!e.a.visible||!e.b.visible) return;
      ctx.beginPath();

      // In tree mode, draw curved lines for parent/child
      if (currentLayout === 'tree' && (e.type==='parent'||e.type==='child')) {
        const from = e.type==='parent'?e.a:e.b;
        const to = e.type==='parent'?e.b:e.a;
        const midY = (from.y+to.y)/2;
        ctx.moveTo(from.x,from.y);
        ctx.bezierCurveTo(from.x,midY,to.x,midY,to.x,to.y);
      } else {
        ctx.moveTo(e.a.x,e.a.y);ctx.lineTo(e.b.x,e.b.y);
      }

      const eColor = REL_COLORS[e.type]||'#607d8b';
      ctx.strokeStyle = eColor + (e.active!==false?'50':'20');
      ctx.lineWidth = FAMILY_TYPES.has(e.type) ? 2 : 1;
      ctx.stroke();

      if (showLabels && scale > 0.6) {
        const mx=(e.a.x+e.b.x)/2, my=(e.a.y+e.b.y)/2;
        ctx.fillStyle=eColor+'60';ctx.font='8px JetBrains Mono';ctx.textAlign='center';
        ctx.fillText(REL_LABELS[e.type]||e.type,mx,my-4);
      }
    });

    // Nodes
    nodes.forEach(n => {
      if (!n.visible) return;
      const isH = hoveredNode===n;
      const r = n.radius*(isH?1.15:1);

      ctx.beginPath();ctx.arc(n.x,n.y,r+6,0,Math.PI*2);
      ctx.fillStyle=n.fav?'rgba(255,235,59,0.06)':'rgba(0,255,65,0.04)';
      if(isH) ctx.fillStyle='rgba(0,255,65,0.12)';
      ctx.fill();

      let nodeColor = n.fav?'#ffeb3b':'#00ff41';
      if (n.tag_colors&&n.tag_colors.length) nodeColor=n.tag_colors[0];

      ctx.beginPath();ctx.arc(n.x,n.y,r,0,Math.PI*2);
      ctx.fillStyle='#111820';ctx.fill();
      ctx.strokeStyle=nodeColor;
      ctx.lineWidth=isH?3:(n.fav?2.5:1.5);
      ctx.stroke();

      const initials=n.label.split(' ').map(w=>w[0]||'').join('').toUpperCase().slice(0,2);
      ctx.fillStyle=nodeColor;
      ctx.font=`bold ${n.fav?13:10}px IBM Plex Sans`;
      ctx.textAlign='center';ctx.textBaseline='middle';
      ctx.fillText(initials,n.x,n.y);

      if (showLabels) {
        ctx.fillStyle=isH?'#fff':'#c9d6df';
        ctx.font=`${isH?12:10}px JetBrains Mono`;
        ctx.textAlign='center';ctx.textBaseline='top';
        ctx.fillText(n.label,n.x,n.y+r+5);
      }

      if (n.fav) { ctx.fillStyle='#ffeb3b';ctx.font='10px sans-serif';ctx.textAlign='center';ctx.fillText('★',n.x+r-2,n.y-r+2); }

      if (n.tag_colors&&n.tag_colors.length>1) {
        n.tag_colors.forEach((tc,i) => {
          const a=(2*Math.PI*i)/n.tag_colors.length-Math.PI/2;
          ctx.beginPath();ctx.arc(n.x+(r+10)*Math.cos(a),n.y+(r+10)*Math.sin(a),3,0,Math.PI*2);
          ctx.fillStyle=tc;ctx.fill();
        });
      }
    });

    ctx.restore();
  }

  // ==================== Animation Loop ====================
  function tick() { simulate(); draw(); requestAnimationFrame(tick); }

  // ==================== Tooltip ====================
  const tooltip=document.getElementById('tooltip');
  const ttName=document.getElementById('tt-name'),ttInfo=document.getElementById('tt-info'),ttTags=document.getElementById('tt-tags');

  function showTT(node,mx,my) {
    ttName.textContent=node.label;
    let info=[];
    if(node.company) info.push(node.company);
    if(node.job_title) info.push(node.job_title);
    info.push(edges.filter(e=>e.a===node||e.b===node).length+' vztahů');
    ttInfo.textContent=info.join(' · ');
    ttTags.innerHTML='';
    if(node.tag_names) node.tag_names.forEach((tn,i) => {
      const el=document.createElement('span');el.className='tt-tag';el.textContent=tn;
      const c=(node.tag_colors&&node.tag_colors[i])||'#00ff41';
      el.style.cssText=`background:${c}25;color:${c};border:1px solid ${c}40`;
      ttTags.appendChild(el);
    });
    tooltip.style.left=(mx+16)+'px';tooltip.style.top=(my-10)+'px';tooltip.style.display='block';
  }

  // ==================== Mouse ====================
  function canvasCoords(e){const r=canvas.getBoundingClientRect();return{x:(e.clientX-r.left-offsetX)/scale,y:(e.clientY-r.top-offsetY)/scale}}
  function screenCoords(e){const r=canvas.getBoundingClientRect();return{x:e.clientX-r.left,y:e.clientY-r.top}}
  function findNode(cx,cy){for(let i=nodes.length-1;i>=0;i--){const n=nodes[i];if(!n.visible)continue;const dx=cx-n.x,dy=cy-n.y;if(dx*dx+dy*dy<n.radius*n.radius*1.5)return n;}return null;}

  canvas.addEventListener('mousedown',e=>{
    const c=canvasCoords(e),node=findNode(c.x,c.y);
    if(node){dragNode=node;canvas.style.cursor='grabbing';}
    else{isPanning=true;panStart={x:e.clientX-offsetX,y:e.clientY-offsetY};canvas.style.cursor='grabbing';}
  });
  canvas.addEventListener('mousemove',e=>{
    const c=canvasCoords(e),s=screenCoords(e);
    if(dragNode){dragNode.x=c.x;dragNode.y=c.y;dragNode.vx=0;dragNode.vy=0;}
    else if(isPanning){offsetX=e.clientX-panStart.x;offsetY=e.clientY-panStart.y;}
    else{const node=findNode(c.x,c.y);if(node){canvas.style.cursor='pointer';hoveredNode=node;showTT(node,s.x,s.y);}else{canvas.style.cursor='grab';hoveredNode=null;tooltip.style.display='none';}}
  });
  canvas.addEventListener('mouseup',()=>{dragNode=null;isPanning=false;canvas.style.cursor=hoveredNode?'pointer':'grab';});
  canvas.addEventListener('mouseleave',()=>{dragNode=null;isPanning=false;hoveredNode=null;tooltip.style.display='none';});
  canvas.addEventListener('click',e=>{if(dragNode)return;const c=canvasCoords(e),node=findNode(c.x,c.y);if(node)window.location.href='/persons/'+node.id+'/';});
  canvas.addEventListener('wheel',e=>{e.preventDefault();const factor=e.deltaY<0?1.1:0.9;const r=canvas.getBoundingClientRect();const mx=e.clientX-r.left,my=e.clientY-r.top;offsetX=mx-(mx-offsetX)*factor;offsetY=my-(my-offsetY)*factor;scale*=factor;scale=Math.max(0.2,Math.min(4,scale));},{passive:false});

  // ==================== Global Controls ====================
  window.setLayout = function(mode) { applyLayout(mode); };
  window.graphZoom = function(f){const cx=W/2,cy=H/2;offsetX=cx-(cx-offsetX)*f;offsetY=cy-(cy-offsetY)*f;scale*=f;scale=Math.max(0.2,Math.min(4,scale));};
  window.graphReset = function(){scale=1;offsetX=0;offsetY=0;nodes.forEach(n=>n.visible=true);document.querySelectorAll('.filter-chip').forEach(c=>c.classList.remove('active'));const first=document.querySelector('.filter-chip');if(first)first.classList.add('active');applyLayout(currentLayout);};
  window.togglePhysics = function(){physicsRunning=!physicsRunning;updatePhysicsBtn();};
  window.toggleLabels = function(){showLabels=!showLabels;document.getElementById('btn-labels').style.color=showLabels?'var(--green)':'var(--muted)';};

  // ==================== Legend & Filters ====================
  function buildLegend() {
    const el=document.getElementById('map-legend');
    let html='<h4>Legenda</h4>';
    if(groups.length){html+='<div class="legend-section"><div class="legend-title">Skupiny</div>';groups.forEach(g=>{html+=`<div class="legend-item" onclick="filterGroup(${g.id})"><span class="legend-rect" style="background:${g.color}15;border-color:${g.color}"></span>${g.name}</div>`;});html+='</div>';}
    if(tags.length){html+='<div class="legend-section"><div class="legend-title">Štítky</div>';tags.forEach(t=>{html+=`<div class="legend-item" onclick="filterTag(${t.id})"><span class="legend-dot" style="background:${t.color}"></span>${t.name}</div>`;});html+='</div>';}
    const usedTypes=new Set(edges.map(e=>e.type));
    if(usedTypes.size){html+='<div class="legend-section"><div class="legend-title">Vztahy</div>';usedTypes.forEach(t=>{html+=`<div class="legend-item"><span class="legend-dot" style="background:${REL_COLORS[t]||'#607d8b'}"></span>${REL_LABELS[t]||t}</div>`;});html+='</div>';}
    el.innerHTML=html;
  }

  function buildFilters(){
    const el=document.getElementById('map-filters');
    let html='<button class="filter-chip active" onclick="clearFilter()">Vše</button>';
    groups.forEach(g=>{html+=`<button class="filter-chip" onclick="filterGroup(${g.id})" data-filter="g${g.id}" style="border-left:3px solid ${g.color}">${g.name}</button>`;});
    tags.forEach(t=>{html+=`<button class="filter-chip" onclick="filterTag(${t.id})" data-filter="t${t.id}">${t.icon||''} ${t.name}</button>`;});
    el.innerHTML=html;
  }

  function setChip(id){document.querySelectorAll('.filter-chip').forEach(c=>c.classList.remove('active'));if(id){const ch=document.querySelector(`[data-filter="${id}"]`);if(ch)ch.classList.add('active');}else{const f=document.querySelector('.filter-chip');if(f)f.classList.add('active');}}
  window.filterGroup=function(gid){setChip('g'+gid);nodes.forEach(n=>{n.visible=n.group_ids&&n.group_ids.includes(gid);});edges.forEach(e=>{if(e.a.visible)e.b.visible=true;if(e.b.visible)e.a.visible=true;});};
  window.filterTag=function(tid){setChip('t'+tid);nodes.forEach(n=>{n.visible=n.tag_ids&&n.tag_ids.includes(tid);});edges.forEach(e=>{if(e.a.visible)e.b.visible=true;if(e.b.visible)e.a.visible=true;});};
  window.clearFilter=function(){setChip(null);nodes.forEach(n=>n.visible=true);};

  // ==================== Init ====================
  resize(); window.addEventListener('resize',resize); loadData();
})();
