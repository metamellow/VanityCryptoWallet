import runpodSdk from 'runpod-sdk';
import dotenv from 'dotenv';

dotenv.config();

const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function manageEndpointJob() {
  try {
    const runpod = runpodSdk(process.env.RUNPOD_API_KEY);
    const endpoint = runpod.endpoint(process.env.ENDPOINT_ID);

    const health = await endpoint.health();
    console.log('Endpoint health:', health);

    if (health.jobs.inProgress > 0 || health.jobs.inQueue > 0) {
      console.log('There are jobs already in progress or queued. Please wait for them to complete.');
      return;
    }

    console.log('Starting a new job...');
    const result = await endpoint.run({
      input: {
        prompt: "Test wallet generation"
      }
    });

    console.log('Job submitted:', result);
    
    if (result && result.id) {
      console.log(`Job started with ID: ${result.id}`);
      
      let jobStatus;
      let initializationTime = 0;
      const maxInitializationTime = 300000; // 5 minutes in milliseconds

      do {
        await delay(10000); // Check every 10 seconds
        jobStatus = await endpoint.status(result.id);
        console.log(`Current job status: ${jobStatus.status}`);
        
        if (jobStatus.status === 'IN_QUEUE') {
          initializationTime += 10000;
          console.log(`Job is still initializing. Time elapsed: ${initializationTime / 1000} seconds`);
          
          if (initializationTime >= maxInitializationTime) {
            console.log('Job initialization is taking longer than expected. You may want to check the RunPod dashboard for more details.');
          }
        }
        
        // Attempt to get logs
        try {
          const logs = await endpoint.getLogs(result.id);
          if (logs && logs.length > 0) {
            console.log('Recent logs:', logs);
          } else {
            console.log('No logs available yet. This is normal during initialization.');
          }
        } catch (logError) {
          console.log('Unable to retrieve logs at this time. This is normal during initialization.');
        }
      } while (jobStatus.status === 'IN_PROGRESS' || jobStatus.status === 'IN_QUEUE');

      if (jobStatus.status === 'COMPLETED') {
        console.log('Job completed successfully. Result:', jobStatus.output);
      } else {
        console.log('Job failed or was cancelled. Status:', jobStatus);
      }
    } else {
      console.log('Job submission failed or returned an unexpected result.');
    }
  } catch (error) {
    console.error('Error interacting with endpoint:', error);
  }
}

manageEndpointJob();