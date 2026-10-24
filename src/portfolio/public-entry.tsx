import React from 'react';
import {createRoot} from 'react-dom/client';
import PublicPortfolio from './PublicPortfolio';
const element=document.getElementById('portfolio-data');
const root=document.getElementById('portfolio-root');
if(element&&root){try{createRoot(root).render(<React.StrictMode><PublicPortfolio site={JSON.parse(element.textContent||'{}')}/></React.StrictMode>);}catch{root.textContent='This portfolio package could not be read. Ask the owner for a fresh approved export.';}}
