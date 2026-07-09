/*
  CPOS UTB - Interacciones básicas de la maqueta adaptada a Django.
  Maneja selector de rol demo, mensajes toast, tabs y modales visuales.
*/
(function(){
  const roles={maestrante:'Maestrante',tutor:'Docente tutor',coordinador:'Coordinador de programa',supervisor:'Supervisor general'};
  const roleKey='cpos_role';
  const current=localStorage.getItem(roleKey)||'maestrante';

  document.querySelectorAll('[data-role-current]').forEach(el=>{el.textContent=roles[current]||roles.maestrante});

  document.querySelectorAll('.role-select').forEach(sel=>{
    sel.value=current;
    sel.addEventListener('change',()=>{
      localStorage.setItem(roleKey,sel.value);
      toast('Vista cambiada a '+roles[sel.value]);
      setTimeout(()=>location.reload(),450);
    });
  });

  document.querySelectorAll('[data-toast]').forEach(btn=>btn.addEventListener('click',()=>toast(btn.getAttribute('data-toast'))));

  document.querySelectorAll('[data-tab]').forEach(btn=>btn.addEventListener('click',()=>{
    document.querySelectorAll('[data-tab]').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    toast('Filtro aplicado: '+btn.textContent.trim());
  }));

  document.querySelectorAll('[data-modal]').forEach(btn=>btn.addEventListener('click',()=>{
    const m=document.getElementById(btn.getAttribute('data-modal'));
    if(m) m.classList.add('open');
  }));

  document.querySelectorAll('[data-close-modal]').forEach(btn=>btn.addEventListener('click',()=>{
    const modal = btn.closest('.modal');
    if(modal) modal.classList.remove('open');
  }));

  document.querySelectorAll('.modal').forEach(m=>m.addEventListener('click',e=>{if(e.target===m)m.classList.remove('open')}));

  document.querySelectorAll('[data-year]').forEach(el=>el.textContent=new Date().getFullYear());

  function toast(msg){
    let t=document.querySelector('.toast');
    if(!t){t=document.createElement('div');t.className='toast';document.body.appendChild(t);}
    t.textContent=msg;
    t.classList.add('show');
    clearTimeout(window.__toast);
    window.__toast=setTimeout(()=>t.classList.remove('show'),2400);
  }
})();
