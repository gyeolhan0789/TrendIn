/**
 * 만들어 낸 파일을 기기로 내려 줍니다.
 *
 * 서버에 내보내기 API가 없어 화면이 들고 있는 값으로 그 자리에서 파일을 만듭니다. 그래서
 * 주소를 만들어 쓰고 곧바로 거둡니다. 거두지 않으면 탭을 닫을 때까지 메모리에 남습니다.
 */
export function downloadFile(fileName: string, content: string, mime: string) {
  const url = URL.createObjectURL(new Blob([content], { type: `${mime};charset=utf-8` }));
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/**
 * CSV 한 칸을 감쌉니다. 쉼표·따옴표·줄바꿈이 든 값은 따옴표로 묶고, 안의 따옴표는 겹쳐 씁니다.
 */
function csvCell(value: string) {
  return /[",\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/**
 * 줄과 칸을 CSV 한 장으로 엮습니다.
 *
 * 앞에 BOM 을 답니다. 엑셀은 이 표시가 없으면 UTF-8 을 시스템 인코딩으로 읽어서 한글이 깨집니다.
 */
export function toCsv(header: string[], rows: string[][]) {
  return `\uFEFF${[header, ...rows].map((row) => row.map(csvCell).join(',')).join('\r\n')}\r\n`;
}

/** 파일 이름에 붙일 오늘 날짜(YYYY-MM-DD). 같은 자료를 여러 날 받아도 섞이지 않습니다. */
export function today() {
  const day = new Date();
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;
}
