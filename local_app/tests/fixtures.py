"""Synthetic records only; no personal viewing history."""
def history(index=0):
    return {'history_key':f'synthetic-{index}', 'hive_key':f'synthetic-{index}',
            'bangumi':{'id':100000+index%191,'name':f'Test season {index%191}',
                       'images':{},'tags':[],'aliases':[]},
            'last_watch_episode':1,'last_watch_time':'2026-01-03T00:00:00Z',
            'progresses':[{'key':1,'episode':1,'road':0,'progress_ms':10000,'updated_at_ms':0}]}
