import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MainWorkspace from './layouts/MainWorkspace';
import FactoryOverview from './components/Explorer/FactoryOverview';
import DataCanvas from './components/Explorer/DataCanvas';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainWorkspace />}>
          <Route index element={<FactoryOverview />} />
          <Route path="pipeline/:id" element={<DataCanvas />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
