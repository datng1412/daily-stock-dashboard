import type {
  VietnamForeignFlowSignalDirectionState,
  VietnamForeignFlowSignalMomentumState,
  VietnamForeignFlowSignals,
} from '../../api/stocks';

export const foreignFlowSignalLabel = (
  state: VietnamForeignFlowSignalDirectionState | VietnamForeignFlowSignalMomentumState | VietnamForeignFlowSignals['intensity']['state'],
): string => ({
  accumulating: 'Tích lũy',
  distributing: 'Phân phối',
  neutral: 'Trung tính',
  unavailable: 'Không đủ dữ liệu',
  accelerating: 'Gia tốc',
  decelerating: 'Chậm lại',
  stable: 'Ổn định',
  reversal: 'Đảo chiều',
  elevated: 'Bất thường cao',
  normal: 'Bình thường',
}[state]);
