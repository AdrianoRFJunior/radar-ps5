import React from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Legend,
} from 'recharts';
import { formatBRL, formatShortDateSP } from '../services/api';

export function PriceHistoryAreaChart({ data = [], meanPrice = null, minPrice = null }) {
  if (!data || data.length === 0) {
    return (
      <div className="h-72 flex items-center justify-center bg-[#090f14] rounded-xl border border-[#1c2d38] text-slate-400 text-sm">
        Nenhum ponto histórico encontrado para o filtro selecionado.
      </div>
    );
  }

  const formatted = data.map((d) => ({
    ...d,
    dateLabel: formatShortDateSP(d.recorded_at),
  }));

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={formatted} margin={{ top: 12, right: 20, left: 10, bottom: 5 }}>
          <defs>
            <linearGradient id="radarGreenGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.45} />
              <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1c2d38" />
          <XAxis dataKey="dateLabel" stroke="#8b9bb4" tick={{ fontSize: 11 }} />
          <YAxis
            stroke="#8b9bb4"
            tick={{ fontSize: 11 }}
            domain={['auto', 'auto']}
            tickFormatter={(v) => `R$${v}`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#0d141a',
              borderColor: '#10b981',
              borderRadius: '0.5rem',
              fontSize: '12px',
            }}
            formatter={(val, name) => [
              formatBRL(val),
              name === 'compared_value'
                ? 'Preço Final Comparado'
                : name === 'price_card'
                ? 'Preço Cartão'
                : name,
            ]}
            labelFormatter={(label, payload) => {
              const p = payload?.[0]?.payload;
              return p
                ? `${label} — ${p.store_name} (${p.payment_condition})`
                : label;
            }}
          />
          <Legend />
          {meanPrice && (
            <ReferenceLine
              y={meanPrice}
              stroke="#eab308"
              strokeDasharray="4 4"
              label={{ value: `Média: ${formatBRL(meanPrice)}`, fill: '#eab308', fontSize: 11, position: 'insideTopRight' }}
            />
          )}
          {minPrice && (
            <ReferenceLine
              y={minPrice}
              stroke="#00e676"
              strokeDasharray="3 3"
              label={{ value: `Mínimo: ${formatBRL(minPrice)}`, fill: '#00e676', fontSize: 11, position: 'insideBottomRight' }}
            />
          )}
          <Area
            type="monotone"
            dataKey="compared_value"
            name="Preço Final (c/ Frete & Cupom)"
            stroke="#10b981"
            strokeWidth={2.5}
            fillOpacity={1}
            fill="url(#radarGreenGrad)"
          />
          <Area
            type="monotone"
            dataKey="price_card"
            name="Preço Cartão Parcelado"
            stroke="#38bdf8"
            strokeWidth={1.5}
            fillOpacity={0}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function BestTimesBarChart({
  data = [],
  xKey = 'hour_label',
  bar1Key = 'drops_count',
  bar1Name = 'Quedas de Preço',
  bar2Key = 'offers_count',
  bar2Name = 'Ofertas Identificadas',
}) {
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 16, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1c2d38" />
          <XAxis dataKey={xKey} stroke="#8b9bb4" tick={{ fontSize: 11 }} />
          <YAxis stroke="#8b9bb4" tick={{ fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: '#0d141a',
              borderColor: '#1c2d38',
              borderRadius: '0.5rem',
              fontSize: '12px',
            }}
          />
          <Legend />
          <Bar dataKey={bar1Key} name={bar1Name} fill="#10b981" radius={[4, 4, 0, 0]} />
          {bar2Key && (
            <Bar dataKey={bar2Key} name={bar2Name} fill="#0284c7" radius={[4, 4, 0, 0]} />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
