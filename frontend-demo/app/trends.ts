export type CategoryId = 'dev' | 'fashion' | 'game' | 'travel' | 'beauty' | 'music' | 'content' | 'finance' | 'sports';
export type Period = 'day' | 'week' | 'month';
export type Trend = { id: string; name: string; sub: string; tag: string; category: CategoryId; mentions: number; growth: number; change: number | 'NEW'; kind: 'top' | 'new' | 'rising'; period: Period };
type Entry = [string, string, string];
type Category = { id: CategoryId; name: string; icon: string; focus: [string, string]; summary: string; insight: string; keywords: string[]; top: Entry[]; fresh: Entry[]; rising: Entry[] };

// Entirely fictional editorial fixtures for UI evaluation, not live trend findings.
export const categories: Category[] = [
  { id:'dev', name:'개발', icon:'</>', focus:['AI가 답을 넘어','행동하기 시작했다.'], summary:'질문에 답하던 AI가 이제 직접 도구를 쓰고, 일을 끝냅니다. 다음 흐름은 ‘실행’에 있습니다.', insight:'더 똑똑한 모델에서, 실제로 일하는 AI로.', keywords:['Agentic Workflow','MCP','AI Coding','Multi-agent'],
    top:[['AI Agent','답변하는 AI에서, 실행하는 AI로','인공지능'],['Vibe Coding','코드보다 의도가 먼저인 개발','개발 문화'],['MCP','AI와 도구를 연결하는 새로운 표준','AI 인프라'],['Local LLM','내 기기에서 직접 실행하는 언어 모델','오픈소스'],['Rust','더 안전하고 빠른 시스템을 향해','프로그래밍']],
    fresh:[['Agent-to-Agent','에이전트끼리 소통하기 시작했어요.','AI 인프라'],['Context Engineering','프롬프트를 넘어, 맥락을 설계하는 기술.','개발 도구'],['Spec-driven Development','명세에서 시작하는 새로운 개발 방식.','개발 문화']],
    rising:[['React Server Components','서버 중심 렌더링이 다시 대화의 중심으로.','웹 프레임워크'],['WebAssembly','브라우저 밖으로 넓어지는 가능성.','개발 환경'],['Edge Computing','사용자와 더 가까운 곳에서 실행해요.','인프라']] },
  { id:'fashion', name:'패션', icon:'♧', focus:['오래된 취향이','새로운 감각이 된다.'], summary:'옷장 속 오래된 아이템이 새로운 조합을 만납니다. 스타일의 기준은 유행보다 나만의 이야기입니다.', insight:'빠르게 바뀌는 유행에서, 오래 남는 취향으로.', keywords:['Archive Fashion','Secondhand','Upcycling','Personal Style'],
    top:[['Neo Vintage','시간이 만든 스타일을 지금의 감각으로','빈티지'],['Ballet Sneakers','가벼운 실루엣과 스포티한 감각의 만남','슈즈'],['Utility Wear','실용성이 곧 스타일이 되는 순간','스트리트'],['Suede Bags','부드러운 질감이 만드는 자연스러운 멋','액세서리'],['Modern Prep','단정함에 더하는 새로운 비율','스타일']],
    fresh:[['Poetcore','문학적인 분위기를 입는 방식.','스타일'],['Hybrid Footwear','서로 다른 신발의 경계가 사라져요.','슈즈'],['Reworked Denim','이미 있는 데님에서 시작하는 새 옷.','업사이클링']],
    rising:[['Archive Fashion','과거 컬렉션이 새로운 영감으로.','빈티지'],['Gorpcore','아웃도어가 일상에 다시 스며들어요.','스타일'],['Handmade Accessories','손으로 만든 디테일을 찾아요.','액세서리']] },
  { id:'game', name:'게임', icon:'⊞', focus:['이기는 게임에서','함께 머무는 세계로.'], summary:'경쟁의 속도보다 함께 보내는 시간이 중요해집니다. 플레이어는 기록을 넘어 관계와 경험을 찾습니다.', insight:'더 높은 점수에서, 더 오래 함께하는 경험으로.', keywords:['Co-op','Cozy Games','UGC','Social Play'],
    top:[['Cozy Co-op','함께 쉬어가는 새로운 플레이 방식','협동 게임'],['AI NPC','매번 다른 대화가 만드는 살아 있는 세계','게임 기술'],['Extraction RPG','탐험과 탈출 사이의 새로운 긴장감','장르'],['User-made Worlds','플레이어가 직접 만드는 놀이터','UGC'],['Handheld Gaming','어디에서나 이어지는 나의 플레이','플랫폼']],
    fresh:[['Social Sandbox','규칙보다 관계가 먼저인 게임.','소셜'],['Voice-driven Play','목소리가 새로운 컨트롤러가 돼요.','인터랙션'],['Tiny Open World','작지만 밀도 높은 탐험의 시작.','인디 게임']],
    rising:[['Couch Co-op','같은 공간에서 함께하는 즐거움.','협동 게임'],['Pixel Art RPG','작은 픽셀로 전하는 깊은 이야기.','인디 게임'],['Game Modding','게임의 가능성을 직접 넓혀요.','커뮤니티']] },
  { id:'travel', name:'여행', icon:'↗', focus:['더 많은 장소보다','더 깊이 머무는 시간.'], summary:'빼곡한 일정 대신 동네의 일상을 여행합니다. 여행의 밀도는 방문한 곳의 수로 정해지지 않습니다.', insight:'많이 보는 여행에서, 깊이 머무는 여행으로.', keywords:['Slow Travel','Local Living','Rail Journey','Off-season'],
    top:[['Slow Travel','속도를 늦추면 보이는 여행의 풍경','여행 방식'],['Coolcation','더위를 피해 찾아가는 시원한 휴식','휴양'],['Rail Journey','이동하는 시간도 여행의 일부로','교통'],['Local Stay','관광지보다 동네의 일상 속으로','숙박'],['Night Tourism','해가 진 뒤 시작되는 또 다른 여행','체험']],
    fresh:[['Book Retreat','책 한 권과 함께 떠나는 휴식.','테마 여행'],['Micro Adventure','가까운 곳에서 발견하는 작은 모험.','아웃도어'],['Silent Travel','소음을 덜어내는 새로운 여행.','휴양']],
    rising:[['Solo Travel','혼자라서 더 자유로운 여정.','여행 방식'],['Farm Stay','자연의 리듬에 맞춰 머물러요.','숙박'],['Walking Tour','두 발로 발견하는 도시의 표정.','체험']] },
  { id:'beauty', name:'뷰티', icon:'◇', focus:['더 많은 단계보다','나에게 맞는 루틴.'], summary:'제품을 더하기보다 나에게 필요한 것을 고릅니다. 꾸준하게 이어갈 수 있는 일상이 새로운 뷰티의 기준입니다.', insight:'복잡한 단계에서, 나에게 맞는 단순함으로.', keywords:['Skinimalism','Barrier Care','Refill','Personal Routine'],
    top:[['Skinimalism','적게 바르고 나에게 집중하는 루틴','스킨케어'],['Barrier Care','피부 기본기를 다시 살피는 흐름','스킨케어'],['Soft Matte','가볍고 자연스러운 새로운 질감','메이크업'],['Refill Beauty','다시 채우며 사용하는 아름다움','지속가능성'],['Scalp Routine','두피도 일상의 관리 루틴으로','헤어']],
    fresh:[['Mood Makeup','기분에 따라 표현하는 오늘의 얼굴.','메이크업'],['Waterless Beauty','물 사용을 줄인 새로운 제형.','제품'],['Scent Layering','향을 조합해 나를 표현해요.','향수']],
    rising:[['Lip Tint','가볍게 물들이는 데일리 컬러.','메이크업'],['Solid Shampoo','작은 고체에 담은 간결한 루틴.','헤어'],['DIY Nail Art','손끝에 담는 작은 창작.','네일']] },
  { id:'music', name:'음악', icon:'♫', focus:['알고리즘 너머','나만의 소리를 찾다.'], summary:'추천 목록에서 한발 벗어나 취향의 맥락을 찾습니다. 음악은 듣는 시간을 넘어 나누는 경험이 됩니다.', insight:'흘려듣는 플레이리스트에서, 직접 고르는 한 곡으로.', keywords:['Listening Bar','Vinyl','Indie Scene','Live Session'],
    top:[['Listening Culture','음악 한 곡에 집중하는 새로운 습관','감상 문화'],['Indie Pop','작은 씬에서 발견하는 새로운 목소리','장르'],['Live Sessions','공간의 분위기까지 전하는 라이브','콘텐츠'],['Ambient Music','일상의 속도를 조절하는 사운드','장르'],['Vinyl Collecting','손에 잡히는 음악의 매력','컬렉션']],
    fresh:[['Micro Festival','취향이 모이는 작은 페스티벌.','공연'],['Spatial Listening','소리에 둘러싸이는 새로운 경험.','오디오'],['Community Radio','동네의 취향을 연결하는 주파수.','커뮤니티']],
    rising:[['City Pop','익숙한 도시의 리듬을 다시 발견해요.','장르'],['Band Sound','함께 만드는 소리의 에너지.','장르'],['Acoustic Covers','한 곡을 새로운 목소리로 만나봐요.','콘텐츠']] },
  { id:'content', name:'콘텐츠', icon:'▷', focus:['짧은 주목을 넘어','오래 남는 이야기로.'], summary:'스쳐가는 영상 사이에서 다시 찾아보는 이야기가 떠오릅니다. 깊은 맥락과 고유한 시선이 관심을 이어갑니다.', insight:'빠르게 넘기는 콘텐츠에서, 다시 찾는 이야기로.', keywords:['Video Essay','Niche Community','Long-form','Creator-led'],
    top:[['Video Essay','하나의 주제를 깊이 파고드는 영상','영상'],['Micro Drama','짧은 호흡으로 이어가는 이야기','드라마'],['Creator Documentary','창작자의 시선으로 담아낸 일상','다큐멘터리'],['Niche Newsletter','작은 관심사에 깊이 있는 큐레이션','텍스트'],['Slow Content','편안하게 오래 머무는 콘텐츠','라이프스타일']],
    fresh:[['Interactive Story','보는 사람의 선택으로 달라지는 이야기.','인터랙티브'],['Audio Journal','목소리로 기록하는 하루의 생각.','오디오'],['Community Zine','작은 커뮤니티가 직접 만드는 매체.','출판']],
    rising:[['Long-form Interview','긴 대화에서 발견하는 진짜 맥락.','인터뷰'],['Webtoon Adaptation','웹툰의 세계가 화면으로 넓어져요.','영상'],['Personal Blog','자신의 공간에 다시 쌓는 이야기.','텍스트']] },
  { id:'finance', name:'금융', icon:'◈', focus:['거대한 숫자보다','내 일상의 돈 이야기.'], summary:'쉽게 이해하고 스스로 선택하려는 관심이 모입니다. 일상의 소비와 돈의 흐름을 들여다보는 콘텐츠를 발견합니다.', insight:'복잡한 용어에서, 이해할 수 있는 일상의 이야기로.', keywords:['Money Diary','Financial Literacy','Open Banking','Budgeting'],
    top:[['Money Journaling','기록으로 돌아보는 일상의 소비','소비 문화'],['Open Banking','한곳에서 연결해 보는 금융 생활','핀테크'],['Finfluencer','금융을 일상의 언어로 이야기하는 사람들','콘텐츠'],['Cashless Travel','현금 없이 연결되는 해외 결제 경험','결제'],['Subscription Audit','반복되는 지출을 다시 살펴보는 습관','소비 문화']],
    fresh:[['Value Spending','나의 가치관을 반영하는 소비.','소비 문화'],['Family Money Talk','가족이 함께 나누는 돈 이야기.','금융 교육'],['Pocket Accounting','작은 기록으로 시작하는 생활 회계.','생활 금융']],
    rising:[['Budget Diary','예산을 기록하는 습관이 다시 관심을 받아요.','생활 금융'],['Financial Literacy','개념부터 스스로 이해하려는 움직임.','금융 교육'],['Local Currency','동네 안에서 순환하는 소비의 흐름.','지역 경제']] },
  { id:'sports', name:'스포츠', icon:'◎', focus:['더 빠른 기록보다','함께 달리는 즐거움.'], summary:'운동이 성과를 넘어 일상의 연결점이 됩니다. 가벼운 시작과 꾸준한 만남이 새로운 스포츠 문화를 만듭니다.', insight:'혼자 세우는 기록에서, 함께 만드는 습관으로.', keywords:['Run Club','Social Fitness','Outdoor','Daily Movement'],
    top:[['Social Running','기록보다 만남이 먼저인 러닝','러닝'],['Pickleball','가볍게 시작하는 새로운 라켓 스포츠','라켓'],['Hybrid Training','다양한 움직임으로 넓히는 운동 경험','피트니스'],['Bouldering','작은 벽에서 찾는 도전의 즐거움','클라이밍'],['Everyday Cycling','일상 속 이동이 운동이 되는 순간','사이클']],
    fresh:[['Coffee Run','달리기 후 커피 한 잔으로 이어지는 만남.','러닝'],['Urban Hiking','도심에서 발견하는 새로운 산책 코스.','아웃도어'],['Community Court','동네 코트에서 시작되는 스포츠 모임.','커뮤니티']],
    rising:[['Trail Running','길을 벗어나 자연 속으로 달려요.','러닝'],['Jump Rope','작은 도구로 다시 시작하는 운동.','피트니스'],['Social Tennis','테니스가 새로운 만남의 장으로.','라켓']] },
];
export const periodLabels: Record<Period,string> = { day:'24시간',week:'7일',month:'30일' };
export const periods: Period[] = ['day','week','month'];
export function getCategory(id: CategoryId) { return categories.find(c=>c.id===id) ?? categories[0]; }
export function getTrends(id: CategoryId, kind: Trend['kind'] = 'top', period: Period = 'day'): Trend[] {
  const c=getCategory(id); const entries=kind==='top'?c.top:kind==='new'?c.fresh:c.rising;
  const order=kind==='top'?(period==='week'?[2,0,1,3,4]:period==='month'?[1,3,0,4,2]:[0,1,2,3,4]):[0,1,2];
  const categoryFactor=1-categories.indexOf(c)*.047;
  const periodFactor=period==='day'?1:period==='week'?5.8:21.4;
  return order.map((idx,rank)=>({ id:`${id}-${kind}-${idx}`,name:entries[idx][0],sub:entries[idx][1],tag:entries[idx][2],category:id,kind,period,
    mentions:Math.round((kind==='top'?[24860,18420,15730,12580,9240][rank]:kind==='new'?[1840,1260,890][rank]:[6240,4530,3260][rank])*categoryFactor*periodFactor),
    growth:Math.round((kind==='top'?[128.4,86.2,214.6,42.8,23.1][idx]:kind==='new'?[0,0,0][rank]:[186,142,98][rank])*(period==='day'?1:period==='week'?.82:.61)*10)/10,
    change:kind==='new'?'NEW':(period==='day'?[2,3,'NEW',-1,0]:period==='week'?[1,-1,2,0,'NEW']:[2,0,1,-2,3])[rank] as number|'NEW' }));
}
export const allTrends = categories.flatMap(c=>(['top','new','rising'] as const).flatMap(k=>getTrends(c.id,k)));
export const getTrend = (id: string) => allTrends.find(t=>t.id===id);
