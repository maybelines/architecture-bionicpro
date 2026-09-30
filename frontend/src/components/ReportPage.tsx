import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

type ReportRow = {
  report_date: string;
  prosthesis_id: string;
  customer_name: string;
  model: string;
  events_count: number;
  movements_count: number;
  avg_response_ms: number;
  avg_battery: number;
};

type Report = {
  date_from: string;
  date_to: string;
  rows: ReportRow[];
};

const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [dateFrom, setDateFrom] = useState(yesterday);
  const [dateTo, setDateTo] = useState(yesterday);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);

  const getReport = async () => {
    if (!keycloak.authenticated) {
      setError('Сначала войдите в систему');
      return;
    }
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      await keycloak.updateToken(30);
      const query = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
      const response = await fetch(`${process.env.REACT_APP_API_URL}/reports?${query}`, {
        headers: { Authorization: `Bearer ${keycloak.token}` }
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Не удалось получить отчёт');
      }
      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось получить отчёт. Попробуйте войти повторно.');
    } finally {
      setLoading(false);
    }
  };

  const downloadReport = () => {
    if (!report) return;
    const file = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(file);
    const link = document.createElement('a');
    link.href = url;
    link.download = `report-${report.date_from}-${report.date_to}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (!initialized) return <div>Загрузка...</div>;

  if (!keycloak.authenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <button onClick={() => keycloak.login()} className="px-4 py-2 bg-blue-500 text-white rounded">
          Войти
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-6xl mx-auto p-6 bg-white rounded shadow">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Отчёт о работе протезов</h1>
          <button onClick={() => keycloak.logout({ redirectUri: window.location.origin })}>Выйти</button>
        </div>
        <p className="mb-4">Данные обновляются раз в сутки. Даты указаны по UTC.</p>
        <div className="flex flex-wrap gap-4 items-end">
          <label>
            Начало периода
            <input
              type="date"
              value={dateFrom}
              disabled={loading}
              onChange={event => { setDateFrom(event.target.value); setReport(null); }}
              className="block border rounded p-2"
            />
          </label>
          <label>
            Конец периода
            <input
              type="date"
              value={dateTo}
              disabled={loading}
              onChange={event => { setDateTo(event.target.value); setReport(null); }}
              className="block border rounded p-2"
            />
          </label>
          <button
            onClick={getReport}
            disabled={loading || !dateFrom || !dateTo || dateFrom > dateTo}
            className="px-4 py-2 bg-blue-500 text-white rounded disabled:opacity-50"
          >
            {loading ? 'Загрузка...' : 'Получить отчёт'}
          </button>
        </div>

        {error && <p role="alert" className="mt-4 p-3 bg-red-100 text-red-700 rounded">{error}</p>}

        {report && (
          <div className="mt-6">
            <h2 className="text-lg mb-3">{report.date_from} — {report.date_to}</h2>
            {report.rows.length === 0 ? <p>За этот период нет данных о работе ваших протезов.</p> : (
              <>
                <p className="mb-3">{report.rows[0].customer_name}</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr>
                        {['Дата', 'Протез', 'Модель', 'События', 'Движения', 'Средний отклик, мс', 'Средний заряд, %'].map(title => (
                          <th key={title} className="border p-2">{title}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {report.rows.map(row => (
                        <tr key={`${row.report_date}-${row.prosthesis_id}`}>
                          {[row.report_date, row.prosthesis_id, row.model, row.events_count, row.movements_count, row.avg_response_ms, row.avg_battery].map((value, index) => (
                            <td key={index} className="border p-2">{value}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
            <button onClick={downloadReport} className="mt-4 px-4 py-2 bg-blue-500 text-white rounded">
              Скачать JSON
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
