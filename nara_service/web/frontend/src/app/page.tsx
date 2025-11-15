"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";

interface ApiResponse {
  message: string;
  version: string;
}

export default function Home() {
  const [apiData, setApiData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await api.get<ApiResponse>("/");
        setApiData(response.data);
        setError(null);
      } catch (err) {
        setError("FastAPI 서버에 연결할 수 없습니다. http://localhost:8000 확인해주세요.");
        console.error("API Error:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          <h1 className="text-3xl font-bold text-gray-900">
            NARA Service Dashboard
          </h1>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          {/* API Status Card */}
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-xl font-semibold mb-4">FastAPI 연결 상태</h2>

            {loading && (
              <div className="text-gray-600">서버 연결 중...</div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                {error}
              </div>
            )}

            {apiData && (
              <div className="bg-green-50 border border-green-200 rounded p-4">
                <div className="flex items-center mb-2">
                  <div className="w-3 h-3 bg-green-500 rounded-full mr-2"></div>
                  <span className="font-semibold text-green-800">연결됨</span>
                </div>
                <p className="text-gray-700">메시지: {apiData.message}</p>
                <p className="text-gray-700">버전: {apiData.version}</p>
              </div>
            )}
          </div>

          {/* Dashboard Grid */}
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-2">서비스 모니터링</h3>
              <p className="text-gray-600">실시간 서비스 상태를 확인하세요</p>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-2">크롤러 상태</h3>
              <p className="text-gray-600">데이터 수집 현황을 모니터링</p>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-2">통계</h3>
              <p className="text-gray-600">수집된 데이터 통계 정보</p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
