import { Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import History from './pages/History'
import BacktestLab from './pages/BacktestLab'
import Analytics from './pages/Analytics'
import TechnicalAnalysis from './pages/TechnicalAnalysis'
import News from './pages/News'
import Layout from './components/Layout'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="history" element={<History />} />
        <Route path="backtest" element={<BacktestLab />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="technical-analysis" element={<TechnicalAnalysis />} />
        <Route path="news" element={<News />} />
      </Route>
    </Routes>
  )
}

export default App