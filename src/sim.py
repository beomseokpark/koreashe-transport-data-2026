"""장애인콜택시(특장차) 이산사건 배차 시뮬레이터.
- 수요: 실제 2025 탑승 기록(완료 건)의 예정시각·출발/목적 행정동 중심점·실제 승차시간
- 공급: 30분 칸별 근무 차량 수 N[slot] (순위 기반: 순위 < N 이면 근무)
- 배차: 호출 시 가장 빨리 도착하는 빈 차, 없으면 대기열. 차가 비면 대기열에서 (접근시간 − θ×이미 기다린 시간)이 가장 작은 호출
  (θ=0이면 가까운 호출 우선, θ가 크면 먼저 온 호출 우선)
- 이동시간 = c + 우회계수×직선거리/시간대별 속도(데이터에서 추정)
- 빈 차 정책: 'stay'(하차 지점 대기) | 'stage'(MEXCLP 거점: 시간대별 거점 좌표·정원 → 정원이 빈 거점 중 가장 가까운 곳으로 이동)
- 포기(선택): patience[i](분)를 주면 배차 전 대기가 그 시간을 넘는 호출은 대기열에서 빠짐(Brown et al. 2005 방식의 인내시간)
- 기록: sample_min을 주면 그 간격으로 '시스템 안 호출 수'(배차된 차 + 대기열) 표본(ISA용), 차량별·날짜별 주행거리(전기차 점검용)"""
import heapq, numpy as np
from collections import deque

class Sim:
    def __init__(self, req, N, depots, kmh, c=8.0, detour=1.30, min_km=0.5,
                 policy="stay", stages=None, slot_min=30, res_lead=20, theta=0.5, end_guard=None, sample_min=None, patience=None):
        self.r = req; self.N = np.asarray(N, int); self.dep = depots  # (V,2)
        self.kmh = np.asarray(kmh, float); self.c = c; self.det = detour; self.mkm = min_km
        self.policy = policy; self.stages = stages or {}; self.slot = slot_min; self.res_lead = res_lead
        self.V = len(depots); self.theta = theta; self.guard = end_guard; self.sample = sample_min
        self.pat = None if patience is None else np.asarray(patience, float)
        # 순위 r 차량의 '현재 근무가 끝나는 시각'(칸 단위로 미리 계산): 근무 종료 직전 장거리 배차 회피 규칙용
        S = len(self.N); self.end_at = np.zeros((S, self.V))
        nxt = np.full(self.V, S * slot_min, float)
        for k in range(S - 1, -1, -1):
            off_r = np.arange(self.V) >= self.N[k]
            nxt[off_r] = k * slot_min
            self.end_at[k] = nxt

    def tt(self, x0, y0, x1, y1, t):
        km = np.maximum(np.hypot(x1 - x0, y1 - y0) / 1000 * self.det, self.mkm)
        h = (int(t // 60)) % 24
        return self.c + km / self.kmh[h] * 60, km

    def run(self):
        r = self.r; R = len(r)
        sched = r["t"].values; rel = sched - np.where(r["reserved"].values, self.res_lead, 0)
        ox, oy, dx, dy = (r[k].values for k in ["ox", "oy", "dx", "dy"])
        ride = r["ride"].values
        V = self.V
        vx, vy = self.dep[:, 0].astype(float).copy(), self.dep[:, 1].astype(float).copy()
        avail = np.zeros(V)            # 재배치 중이면 이 시각까지 이동 중
        idle = np.zeros(V, bool); onduty = np.zeros(V, bool)
        pickup = np.full(R, np.nan); appr = np.full(R, np.nan)
        dead_km = 0.0; reloc_km = 0.0; ret_km = 0.0; pass_km = 0.0
        ev = []  # (time, kind, id) kind 0=FREE 1=DUTY 2=REQ 3=SAMPLE 4=ABANDON (같은 시각이면 차 반납→근무변경→호출)
        order = np.argsort(rel, kind="stable")
        for i in order: heapq.heappush(ev, (rel[i], 2, int(i)))
        inq = np.zeros(R, bool); aband = np.zeros(R, bool)
        if self.pat is not None:
            for i in np.flatnonzero(np.isfinite(self.pat)): heapq.heappush(ev, (sched[i] + self.pat[i], 4, int(i)))
        nslots = len(self.N)
        for s in range(nslots): heapq.heappush(ev, (s * self.slot, 1, s))
        q = []
        rank = np.arange(V)
        cur_N = 0
        nbusy = 0; samples = []
        ndays = int(np.ceil(nslots * self.slot / 1440)); vkm = np.zeros((ndays, V))
        if self.sample:
            for j in range(int(nslots * self.slot // self.sample)): heapq.heappush(ev, (j * self.sample, 3, j))
        day = lambda t: min(int(t // 1440), ndays - 1)

        def assign(v, i, t):
            nonlocal dead_km, pass_km, nbusy
            nbusy += 1
            a, km = self.tt(vx[v], vy[v], ox[i], oy[i], t)
            a += max(0.0, avail[v] - t)
            p = max(t + a, sched[i])
            pickup[i] = p; appr[i] = a; dead_km += km; site[v] = -1
            ride_km = max(np.hypot(dx[i] - ox[i], dy[i] - oy[i]) / 1000 * self.det, self.mkm); pass_km += ride_km
            vkm[day(t), v] += km + ride_km
            idle[v] = False
            vx[v], vy[v] = dx[i], dy[i]
            heapq.heappush(ev, (p + ride[i], 0, v))

        def pick(v, t):
            qa = np.fromiter(q, int, len(q))
            if self.guard is not None:
                k_ = min(int(t // self.slot), len(self.N) - 1)
                ok = self.end_at[k_, v] + self.guard >= t + 30 + ride[qa]
                if not ok.any(): return None
                qa = qa[ok]
            km = np.maximum(np.hypot(ox[qa] - vx[v], oy[qa] - vy[v]) / 1000 * self.det, self.mkm)
            score = km / self.kmh[int(t // 60) % 24] * 60 - self.theta * (t - rel[qa])
            i = int(qa[int(score.argmin())]); q.remove(i); inq[i] = False; return i

        site = np.full(V, -1); site_h = np.full(V, -1)

        def go_idle(v, t):
            nonlocal reloc_km
            idle[v] = True; avail[v] = t; site[v] = -1
            if self.policy == "stage":
                h = int(t // 60) % 24
                S = self.stages.get(h)
                if S is None: return
                xy, cap = S
                cur = (idle & onduty & (site_h == h) & (site >= 0))
                used = np.bincount(site[cur], minlength=len(cap))
                free = np.flatnonzero(used < cap)
                if len(free) == 0: return
                d = np.hypot(xy[free, 0] - vx[v], xy[free, 1] - vy[v]); j = int(free[d.argmin()])
                site[v] = j; site_h[v] = h
                dd = float(d.min())
                if dd > 500:
                    a, km = self.tt(vx[v], vy[v], xy[j, 0], xy[j, 1], t)
                    reloc_km += km; avail[v] = t + a - self.c   # 거점 이동에는 승차 준비시간 없음
                    vx[v], vy[v] = xy[j]

        def off(v, t=0):
            nonlocal ret_km
            km = max(np.hypot(self.dep[v, 0] - vx[v], self.dep[v, 1] - vy[v]) / 1000 * self.det, 0)
            ret_km += km; vkm[day(t), v] += km; vx[v], vy[v] = self.dep[v]; idle[v] = False; onduty[v] = False

        idle_log = []
        while ev:
            t, kind, k = heapq.heappop(ev)
            if kind == 1:
                idle_log.append((t, int((idle & onduty).sum()), int(onduty.sum())))
            if kind == 3:
                samples.append((t, nbusy, len(q))); continue
            if kind == 4:      # 인내시간 초과: 아직 배차 전이면 포기
                if inq[k]: q.remove(k); inq[k] = False; aband[k] = True
                continue
            if kind == 0:      # 차량 v 하차 완료
                v = k; nbusy -= 1
                if rank[v] >= cur_N:
                    off(v, t); continue
                i = pick(v, t) if q else None
                if i is not None: assign(v, i, t)
                else: go_idle(v, t)
            elif kind == 1:    # 근무 차량 수 변경
                newN = self.N[k]
                if newN > cur_N:
                    for v in range(cur_N, newN):
                        if not onduty[v]:
                            onduty[v] = True; vx[v], vy[v] = self.dep[v]
                            i = pick(v, t) if q else None
                            if i is not None: assign(v, i, t)
                            else: go_idle(v, t)
                else:
                    for v in range(newN, cur_N):
                        if idle[v]: off(v, t)
                cur_N = newN
            else:              # 호출 i
                i = k
                cand = np.flatnonzero(idle & onduty)
                if self.guard is not None and len(cand):
                    k_ = min(int(t // self.slot), len(self.N) - 1)
                    cand = cand[self.end_at[k_, cand] + self.guard >= t + 30 + ride[i]]
                if len(cand) == 0:
                    q.append(i); inq[i] = True; continue
                km = np.maximum(np.hypot(ox[i] - vx[cand], oy[i] - vy[cand]) / 1000 * self.det, self.mkm)
                h = int(t // 60) % 24
                a = self.c + km / self.kmh[h] * 60 + np.maximum(0, avail[cand] - t)
                assign(int(cand[a.argmin()]), i, t)
        wait = pickup - sched
        return dict(wait=wait, appr=appr, aband=aband, idle_log=idle_log, samples=samples, veh_day_km=vkm, dead_km=dead_km, reloc_km=reloc_km, ret_km=ret_km, pass_km=pass_km)
