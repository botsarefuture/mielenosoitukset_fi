"""Slow attendance requests follow the mounted window, not the newest page."""
from pathlib import Path

import pytest


@pytest.mark.e2e
def test_slow_attendance_survives_append_and_cancels_only_eviction_or_search(browser_page):
    browser_page.set_viewport_size({'width': 1280, 'height': 900})
    browser_page.set_content('''<style>.public-list-page{height:600px;overflow-anchor:none}</style>
      <div id="demos-grid"></div><div id="no-results"></div>
      <p id="listing-result-summary" data-format="__START__–__END__ / __COUNT__"></p>
      <div id="listing-load-error" hidden><button>Retry</button></div>''')
    scripts = Path('mielenosoitukset_fi/static/js')
    browser_page.add_script_tag(path=str(scripts / 'user-pagination.js'))
    browser_page.add_script_tag(path=str(scripts / 'demo-card-render.js'))
    result = browser_page.evaluate('''async () => {
      const demos=[],attendance=[];
      document.logged_in=true;
      window.fetch=(url,options)=>new Promise((resolve,reject)=>{
        if(url.startsWith('/api/demonstrations?')) demos.push({resolve,options});
        else {
          attendance.push({resolve,options});
          options.signal.addEventListener('abort',()=>reject(new DOMException('Cancelled','AbortError')),{once:true});
        }
      });
      setup_grid_navigation=()=>{};
      renderDemoCards=(rows,options)=>rows.map(row=>{
        const card=document.createElement('div');card.dataset.demoId=row._id;
        const title=document.createElement('span');title.textContent=row.title;
        const loading=document.createElement('div');loading.className='attending-loading';
        const friends=document.createElement('div');friends.className='demo-card-friends';
        const empty=document.createElement('div');empty.className='demo-card-no-friends';
        card.append(title,loading,friends,empty);options.container.append(card);return card;
      });
      window.publicListWindow=UserPagination.createPageWindow(document.getElementById('demos-grid'));
      const finish=(index,page)=>demos[index].resolve({ok:true,json:async()=>({page,per_page:1,
        total_pages:20,total:20,result_start:page,result_end:page,results:[{_id:String(page),title:`Page ${page}`} ]})});
      for(let page=1;page<=6;page++){
        scrollTo(0,document.body.scrollHeight);
        const request=loadDemos(page,page!==1);finish(page-1,page);await request;
        if(friendsRequests.size>5) throw new Error('Unbounded attendance requests');
      }
      const evicted=attendance[0].options.signal.aborted;
      const retained=attendance.slice(1).every(request=>!request.options.signal.aborted);
      attendance[1].resolve({json:async()=>({})});
      await new Promise(resolve=>requestAnimationFrame(resolve));
      const completed=document.querySelector('[data-list-page="2"] .attending-loading').style.display==='none';
      const replacement=loadDemos(1,false,{search:'new'});finish(6,1);await replacement;
      return {evicted,retained,completed,
        oldCancelled:attendance.slice(2,6).every(request=>request.options.signal.aborted),
        currentActive:!attendance[6].options.signal.aborted,
        pending:friendsRequests.size,pages:document.querySelectorAll('.public-list-page').length};
    }''')
    assert result == {'evicted': True, 'retained': True, 'completed': True,
                      'oldCancelled': True, 'currentActive': True, 'pending': 1, 'pages': 1}
