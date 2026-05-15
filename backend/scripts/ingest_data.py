#!/usr/bin/env python3
"""
RankRoute Backend - Data Ingestion Script
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import uuid
from app.config import settings
from app.core.chroma_client import chroma_client
from typing import List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataIngestor:
    def __init__(self):
        self.chroma = chroma_client
    
    def ingest_cee_csv(self, csv_path: str = None):
        path = csv_path or settings.cee_data_path
        
        if not os.path.exists(path):
            logger.warning(f"CEE CSV not found at {path}")
            return False
        
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} rows from CEE CSV")
        
        df = self._clean_dataframe(df)
        
        documents, metadatas, ids = self._process_cee_rows(df)
        
        self._batch_ingest(documents, metadatas, ids, "cee")
        
        logger.info(f"SUCCESS: Ingested {len(documents)} CEE documents")
        return True
    
    def ingest_jee_csv(self, csv_path: str = None):
        path = csv_path or settings.jee_data_path
        
        if not os.path.exists(path):
            logger.warning(f"JEE CSV not found at {path}")
            return False
        
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} rows from JEE CSV")
        
        df = self._clean_dataframe(df)
        
        documents, metadatas, ids = self._process_jee_rows(df)
        
        self._batch_ingest(documents, metadatas, ids, "jee")
        
        logger.info(f"SUCCESS: Ingested {len(documents)} JEE documents")
        return True
    
    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        columns_map = {
            'college': 'college_name',
            'institute': 'college_name',
            'institute_name': 'college_name',
            'branch_name': 'branch',
            'course': 'branch',
            'open_rank': 'opening_rank',
            'close_rank': 'closing_rank',
            'op_rank': 'opening_rank',
            'cl_rank': 'closing_rank',
        }
        
        df.columns = df.columns.str.strip().str.lower()
        df = df.rename(columns=columns_map)
        df = df.fillna('')
        
        return df
    
    def _process_cee_rows(self, df: pd.DataFrame) -> tuple:
        documents = []
        metadatas = []
        ids = []
        
        for idx, row in df.iterrows():
            doc_text = self._create_cee_document(row)
            
            metadata = {
                'college_name': str(row.get('college_name', '')),
                'college_code': str(row.get('college_code', '')),
                'branch': str(row.get('branch', '')),
                'category': str(row.get('category', 'General')),
                'opening_rank': int(row.get('opening_rank', 0) or 0),
                'closing_rank': int(row.get('closing_rank', 0) or 0),
                'year': int(row.get('year', 2023) or 2023),
                'seat_type': str(row.get('seat_type', 'Government')),
                'source': 'CEE'
            }
            
            round_no = row.get('round', '1')
            doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, 
                f"{metadata['college_name']}_{metadata['branch']}_{metadata['category']}_{metadata['year']}_{round_no}_{idx}"))
            
            documents.append(doc_text)
            metadatas.append(metadata)
            ids.append(doc_id)
        
        return documents, metadatas, ids
    
    def _process_jee_rows(self, df: pd.DataFrame) -> tuple:
        documents = []
        metadatas = []
        ids = []
        
        for idx, row in df.iterrows():
            doc_text = self._create_jee_document(row)
            
            metadata = {
                'college_name': str(row.get('institute_name', row.get('college_name', ''))),
                'branch': str(row.get('branch', '')),
                'category': str(row.get('category', 'General')),
                'opening_rank': int(row.get('opening_rank', 0) or 0),
                'closing_rank': int(row.get('closing_rank', 0) or 0),
                'year': int(row.get('year', 2023) or 2023),
                'quota': str(row.get('quota', 'Home State')),
                'seat_type': str(row.get('seat_type', 'Government')),
                'source': 'JEE'
            }
            
            doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, 
                f"{metadata['college_name']}_{metadata['branch']}_{metadata['category']}_{metadata['quota']}_{metadata['year']}_{idx}"))
            
            documents.append(doc_text)
            metadatas.append(metadata)
            ids.append(doc_id)
        
        return documents, metadatas, ids
    
    def _create_cee_document(self, row: pd.Series) -> str:
        college = row.get('college_name', 'Unknown College')
        branch = row.get('branch', 'Unknown Branch')
        category = row.get('category', 'General')
        opening_rank = row.get('opening_rank', 0)
        closing_rank = row.get('closing_rank', 0)
        year = row.get('year', 2023)
        
        return f"""At {college}, the {branch} branch for the {category} category 
of Assam CEE had an opening rank of {opening_rank} and closing rank of {closing_rank} 
in the year {year}. 

Key Details:
- College: {college}
- Branch/Course: {branch}
- Category: {category}
- Opening Rank (OR): {opening_rank}
- Closing Rank (CR): {closing_rank}
- Year: {year}
- Exam: Assam CEE

Students with ranks between {opening_rank} and {closing_rank} were admitted to this 
branch under the {category} category during the {year} counseling."""
    
    def _create_jee_document(self, row: pd.Series) -> str:
        institute = row.get('institute_name', row.get('college_name', 'Unknown Institute'))
        branch = row.get('branch', 'Unknown Branch')
        category = row.get('category', 'General')
        opening_rank = row.get('opening_rank', 0)
        closing_rank = row.get('closing_rank', 0)
        quota = row.get('quota', 'Home State')
        year = row.get('year', 2023)
        
        return f"""At {institute}, the {branch} branch for the {category} category 
through JEE Mains (JOSAA) had an opening rank of {opening_rank} and closing rank of 
{closing_rank} in the year {year} under {quota} quota.

Key Details:
- Institute: {institute}
- Branch/Course: {branch}
- Category: {category}
- Quota: {quota}
- Opening Rank (OR): {opening_rank}
- Closing Rank (CR): {closing_rank}
- Year: {year}
- Exam: JEE Mains (JOSAA)

Students with ranks between {opening_rank} and {closing_rank} were admitted to this 
branch under the {category} category and {quota} quota during the {year} counseling."""
    
    def _batch_ingest(self, documents, metadatas, ids, collection_name, batch_size=50):
        total = len(documents)
        
        for i in range(0, total, batch_size):
            batch_docs = documents[i:i+batch_size]
            batch_meta = metadatas[i:i+batch_size]
            batch_ids = ids[i:i+batch_size]
            
            self.chroma.add_documents(
                documents=batch_docs,
                metadatas=batch_meta,
                ids=batch_ids,
                collection_name=collection_name
            )
            
            logger.info(f"Progress: {min(i+batch_size, total)}/{total} documents")


def main():
    print("\n" + "="*60)
    print("RANKROUTE DATA INGESTION")
    print("="*60 + "\n")
    
    ingestor = DataIngestor()
    
    ingestor.ingest_cee_csv()
    ingestor.ingest_jee_csv()
    
    print("\n" + "="*60)
    print("INGESTION COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
