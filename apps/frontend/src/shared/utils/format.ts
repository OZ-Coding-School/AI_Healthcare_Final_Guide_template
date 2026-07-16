/**
 * 날짜 및 시간 관련 공통 유틸리티 함수
 */

/**
 * ISO 형식의 날짜 문자열을 사용자 친화적인 형식으로 변환 (예: 2024-07-16 16:47)
 */
export function formatDateTime(dateString: string | null | undefined): string {
  if (!dateString) return "-";
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;

    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");

    return `${year}-${month}-${day} ${hours}:${minutes}`;
  } catch (_e) {
    return dateString;
  }
}

/**
 * ISO 형식의 날짜 문자열을 사용자 친화적인 날짜 형식으로 변환 (예: 2024-07-16)
 */
export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return "-";
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;

    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");

    return `${year}-${month}-${day}`;
  } catch (_e) {
    return dateString;
  }
}

/**
 * 'HH:mm:ss' 또는 'HH:mm' 형식의 시간 문자열을 포맷팅 (예: 14:30)
 */
export function formatTime(timeString: string | null | undefined): string {
  if (!timeString) return "-";
  // 단순히 앞의 5글자(HH:mm)만 추출하거나, 필요에 따라 더 정교하게 처리
  return timeString.substring(0, 5);
}

/**
 * 전화번호를 010-0000-0000 형식으로 변환
 */
export function formatPhoneNumber(phone: string | null | undefined): string {
  if (!phone) return "-";

  // 숫자만 추출
  const cleaned = phone.replace(/\D/g, "");

  // 한국 전화번호 형식 (01012345678 -> 010-1234-5678)
  if (cleaned.length === 11) {
    return cleaned.replace(/(\d{3})(\d{4})(\d{4})/, "$1-$2-$3");
  }

  // 10자리 번호 (021234567 -> 02-123-4567 또는 0101234567 -> 010-123-4567)
  if (cleaned.length === 10) {
    if (cleaned.startsWith("02")) {
      return cleaned.replace(/(\d{2})(\d{3})(\d{4})/, "$1-$2-$3");
    }
    return cleaned.replace(/(\d{3})(\d{3})(\d{4})/, "$1-$2-$3");
  }

  // 기타 형식은 원래 값 반환 또는 기본적인 처리
  if (cleaned.length > 11) {
    // 국제번호 등 (예: 821012345678)
    if (cleaned.startsWith("82")) {
      const rest = cleaned.substring(2);
      if (rest.length === 10) return `0${rest.replace(/(\d{2})(\d{4})(\d{4})/, "$1-$2-$3")}`; // 010-1234-5678로 변환 시도
      return phone;
    }
  }

  return phone;
}
