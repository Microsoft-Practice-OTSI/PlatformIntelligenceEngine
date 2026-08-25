import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MainWorkspace from './layouts/MainWorkspace';
import FactoryOverview from './components/Explorer/FactoryOverview';
import DataCanvas from './components/Explorer/DataCanvas';
import ChangeImpactPanel from './components/ImpactAnalysis/ChangeImpactPanel';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainWorkspace />}>
          <Route index element={<FactoryOverview />} />
          <Route path="pipeline/:id" element={<DataCanvas />} />
          <Route path="impact-analysis/:assetName" element={<ChangeImpactPanelWrapper />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

function ChangeImpactPanelWrapper() {
  const params = new URLSearchParams(window.location.search);
  const objectType = params.get('type') || undefined;
  return <ChangeImpactPanel assetName={decodeURIComponent(window.location.pathname.split('/').pop())} objectType={objectType} onBack={() => window.history.back()} />;
}

export default App;
