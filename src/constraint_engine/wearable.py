"""Evidence-driven wearable budgets; stdlib only, no physiological simulation.

All lengths are millimeters, mass grams, current mA, capacity mAh. Signal and
noise must both be input-referred RMS microvolts over the same bandwidth.
Limits are engineering inputs, never inferred regulatory thresholds.
"""
import math


def _number(value, name, positive=True):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or (value <= 0 if positive else value < 0):
        raise ValueError(name + ' must be a finite ' + ('positive' if positive else 'nonnegative') + ' number')
    return value


def evaluate_wearable(data):
    if not isinstance(data, dict):
        raise ValueError('Wearable inputs must be an object')
    numeric = ('product_length_mm','product_width_mm','product_height_mm','max_length_mm','max_width_mm','max_height_mm','max_mass_g','battery_capacity_mah','average_current_ma','usable_capacity_fraction','required_runtime_hours','minimum_signal_uv_rms','input_noise_uv_rms','noise_bandwidth_hz','required_snr_db')
    for key in numeric:
        if data.get(key) is not None:
            _number(data[key], key)
    if data.get('usable_capacity_fraction') is not None and data['usable_capacity_fraction'] > 1:
        raise ValueError('usable_capacity_fraction must not exceed 1')
    if data.get('mass_items_g') is not None:
        if not isinstance(data['mass_items_g'], dict):
            raise ValueError('mass_items_g must be an object')
        for key, value in data['mass_items_g'].items():
            if value is not None:
                _number(value, key, False)
    checks = []
    def add(key, title, values, compute, limit, comparison, unit, method):
        missing = [k for k in values + [limit] if data.get(k) is None]
        row = dict(id='wearable.' + key, title=title, status='SKIP', measured=None,
                   required=data.get(limit), unit=unit, comparison=comparison, method=method,
                   source='Engineer-supplied brief and evidence', missing=missing)
        if missing:
            row['message'] = 'Supply ' + ', '.join(missing) + ' before evaluating.'
        else:
            required = _number(data[limit], limit)
            measured = compute()
            passed = measured <= required if comparison == '<=' else measured >= required
            row.update(status='PASS' if passed else 'FAIL', measured=round(measured, 6),
                       message=f'{measured:.3f} {unit}; {comparison} {required:g} {unit} required.')
        checks.append(row)
    for axis in ('length', 'width', 'height'):
        measured = 'product_' + axis + '_mm'; limit = 'max_' + axis + '_mm'
        add(axis, 'Wearable ' + axis, [measured], lambda k=measured: _number(data[k], k), limit, '<=', 'mm', 'Product external envelope; orientation-specific, not chest conformity')
    def mass():
        rows = data['mass_items_g']
        if not isinstance(rows, dict) or not rows:
            raise ValueError('mass_items_g must contain every assembly item')
        return sum(_number(v, k, False) for k, v in rows.items())
    # Explicit completeness declaration avoids treating a partial BOM as total mass.
    mass_data = data.get('mass_items_g')
    if data.get('mass_budget_complete') is not True or not isinstance(mass_data, dict) or any(v is None for v in mass_data.values()):
        checks.append(dict(id='wearable.mass', title='Complete wearable mass', status='SKIP', measured=None, required=data.get('max_mass_g'),unit='g',missing=['complete mass budget'],message='Include PCB, components, battery, enclosure, adhesive and electrodes; confirm completeness.',method='Sum of declared item masses'))
    else:
        add('mass','Complete wearable mass',['mass_items_g'],mass,'max_mass_g','<=','g','Sum of complete declared assembly masses')
    def runtime():
        capacity=_number(data['battery_capacity_mah'],'battery_capacity_mah')
        current=_number(data['average_current_ma'],'average_current_ma')
        usable=_number(data['usable_capacity_fraction'],'usable_capacity_fraction')
        if usable>1:raise ValueError('usable_capacity_fraction must not exceed 1')
        return capacity*usable/current
    add('runtime','Battery runtime',['battery_capacity_mah','average_current_ma','usable_capacity_fraction'],runtime,'required_runtime_hours','>=','hours','Usable mAh / average battery-side mA; requires duty cycle, conversion loss and aging evidence')
    def snr():
        _number(data['noise_bandwidth_hz'],'noise_bandwidth_hz')
        return 20*math.log10(_number(data['minimum_signal_uv_rms'],'minimum_signal_uv_rms')/_number(data['input_noise_uv_rms'],'input_noise_uv_rms'))
    add('signal','Input-referred signal/noise budget',['minimum_signal_uv_rms','input_noise_uv_rms','noise_bandwidth_hz'],snr,'required_snr_db','>=','dB','20 log10(signal RMS / noise RMS), same input reference and bandwidth; not diagnostic sensitivity')
    return checks


def compare_checks(before, after):
    """Preserve identity and measurements, including regressions in existing failures."""
    old={c['id']:c for c in before};new={c['id']:c for c in after}
    fixed=[];introduced=[];worsened=[];improved=[];unverified=[]
    for key in sorted(old.keys() | new.keys()):
        a,b=old.get(key),new.get(key)
        # These engine rules emit failures only; disappearance means resolved
        # when evaluating the same parts/rules (enforced by the workflow).
        sparse = key.startswith(('fit.overlap::','fit.courtyard::'))
        if sparse and a and not b and a['status']=='FAIL':
            fixed.append(key);continue
        if not a and b and b['status']=='FAIL':
            introduced.append(key);continue
        if not a or not b or b['status'] in ('SKIP','UNKNOWN','WARN'):
            unverified.append(key);continue
        if a['status']=='FAIL' and b['status']=='PASS':fixed.append(key)
        if b['status']=='FAIL' and a['status']!='FAIL':introduced.append(key)
        # Engine margin is normalized: larger means safer, also for max separation.
        av,bv=a.get('margin_mm'),b.get('margin_mm')
        if isinstance(av,(int,float)) and isinstance(bv,(int,float)):
            if bv<av-1e-6:worsened.append(key)
            if bv>av+1e-6:improved.append(key)
    positive=bool(fixed or improved);negative=bool(introduced or worsened)
    return dict(verdict='mixed' if positive and negative else 'regresses' if negative else 'improves' if positive else 'neutral',fixed=fixed,introduced=introduced,worsened=worsened,improved=improved,unverified=unverified)
