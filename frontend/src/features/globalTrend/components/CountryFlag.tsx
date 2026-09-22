import { useState } from 'react';
import { flagOf } from '../data/countryGeo';

/*
 * 나라 국기를 그림으로 내놓습니다.
 *
 * 국기 이모지를 쓰면 윈도에서는 네모 안에 KR·US 같은 글자 두 개가 섭니다. 윈도에 국기 글꼴이
 * 없어서인데, 그러면 국기 자리가 나라 코드를 한 번 더 적는 자리가 되어 아무것도 더 알려 주지
 * 않습니다. 그림은 어느 기기에서나 같게 보입니다.
 *
 * 그림을 받아 오지 못하거나 국기가 없는 코드(파이프라인이 나라를 못 가린 XX 등)면 코드 두
 * 글자를 그대로 세웁니다. 빈자리로 두면 줄이 밀려 옆 칸과 어긋납니다.
 */

const FLAG_CDN = 'https://flagcdn.com';

interface CountryFlagProps {
  code: string;
  /** 국기 칸의 크기·모양을 정하는 클래스. 쓰는 자리마다 크기가 달라 밖에서 줍니다. */
  className?: string;
}

export function CountryFlag({ code, className = '' }: CountryFlagProps) {
  const [failed, setFailed] = useState(false);
  const normalized = code.trim().toLowerCase();
  /* flagOf 가 빈 값을 주는 코드는 국기가 없는 코드입니다. 그 규칙을 여기서 또 적지 않습니다. */
  const hasFlag = flagOf(code.trim().toUpperCase()) !== '';

  if (failed || !hasFlag) {
    return <span className={`country-flag is-blank ${className}`} aria-hidden="true">{code}</span>;
  }

  return (
    <img
      className={`country-flag ${className}`}
      src={`${FLAG_CDN}/w40/${normalized}.png`}
      srcSet={`${FLAG_CDN}/w40/${normalized}.png 1x, ${FLAG_CDN}/w80/${normalized}.png 2x`}
      /* 나라 이름이 늘 바로 옆에 적혀 있어, 읽어 주면 같은 말을 두 번 듣게 됩니다. */
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}
