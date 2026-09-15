/*
 * 콘텐츠 목록을 내려 주는 API는 아직 트렌드 하나를 기준으로만 있습니다(getRelatedContents).
 * 랜딩은 특정 트렌드에 매여 있지 않아서, 자리와 생김새만 잡아 두고 값은 시안 그대로 둡니다.
 */
export interface LandingContent {
  id: string;
  title: string;
  description: string;
  source: string;
  time: string;
  background: string;
}

export const landingContents: LandingContent[] = [
  {
    id: 'iphone17',
    title: '아이폰17, 무엇이 달라졌나?',
    description: '디자인부터 성능까지, 주요 변화 포인트 정리',
    source: 'IT Daily',
    time: '2시간 전',
    background: 'linear-gradient(135deg, #312e81, #4338ca)',
  },
  {
    id: 'kpop-demon-hunters',
    title: '케이팝 데몬 헌터스, 글로벌 인기 이유',
    description: 'K콘텐츠가 또 한 번 세계를 사로잡다',
    source: 'Trend News',
    time: '3시간 전',
    background: 'linear-gradient(135deg, #374151, #6b7280)',
  },
  {
    id: 'running-crew',
    title: '러닝 크루, 새로운 라이프스타일로',
    description: '함께 달리는 사람들이 늘고 있다',
    source: 'Lifestyle',
    time: '5시간 전',
    background: 'linear-gradient(135deg, #064e3b, #059669)',
  },
  {
    id: 'chuseok-gift',
    title: '추석 선물세트 트렌드 변화',
    description: "올해는 '가성비'와 '프리미엄'의 공존",
    source: 'Economy',
    time: '6시간 전',
    background: 'linear-gradient(135deg, #78716c, #a8a29e)',
  },
];
