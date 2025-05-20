import http from 'k6/http';
import { sleep } from 'k6';

export const options = {
  // Cấu hình để gửi 1000 requests trong 10 giây
  scenarios: {
    constant_request_rate: {
      executor: 'constant-arrival-rate',
      rate: 100,              // 100 requests mỗi giây = 1000 requests trong 10 giây
      timeUnit: '1s',         // Mỗi giây
      duration: '10s',        // Thời gian chạy test là 10 giây
      preAllocatedVUs: 50,    // Số lượng VU (virtual users) khởi tạo
      maxVUs: 100,            // Số lượng VU tối đa nếu cần
    },
  },
};

export default function () {
  // Thay thế URL dưới đây bằng URL của website bạn muốn test
  const response = http.get('http://192.168.2.139');

  // Bạn có thể xem phản hồi và viết các assertions nếu cần
  // console.log(JSON.stringify(response));

  // Có thể thêm kiểm tra phản hồi nếu muốn
  // check(response, {
  //   'status is 200': (r) => r.status === 200,
  // });

  // Thêm một khoảng nghỉ nhỏ giữa các requests của cùng một VU (tuỳ chọn)
  // sleep(0.1);
}
