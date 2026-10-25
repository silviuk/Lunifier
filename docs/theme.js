(()=>{
const root=document.documentElement,select=document.querySelector('#theme-choice'),media=matchMedia('(prefers-color-scheme: dark)');
function apply(){const selected=root.dataset.theme||'system';const dark=selected==='dark'||(selected==='system'&&media.matches);select.value=selected;for(const image of document.querySelectorAll('[data-light-src]'))image.src=dark?image.dataset.darkSrc:image.dataset.lightSrc;for(const source of document.querySelectorAll('[data-light-srcset]'))source.srcset=dark?source.dataset.darkSrcset:source.dataset.lightSrcset;document.querySelector('meta[name="theme-color"]').content=getComputedStyle(root).getPropertyValue('--bg').trim();}
select.addEventListener('change',()=>{const theme=select.value;if(theme==='system')delete root.dataset.theme;else root.dataset.theme=theme;try{if(theme==='system')localStorage.removeItem('site-theme');else localStorage.setItem('site-theme',theme)}catch{}apply()});media.addEventListener('change',apply);apply();
})();
