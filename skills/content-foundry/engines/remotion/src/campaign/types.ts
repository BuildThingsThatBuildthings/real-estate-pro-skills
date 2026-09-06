export type CampaignScene = {photo?: string; secondaryPhoto?: string; type?: string; label: string; headline: string; frames: number; note?: string; bigText?:string; detail?:string};
export type CampaignProps = {
 width:number; height:number; duration:number;
 brand:{name:string; agent:string; brokerage:string; phone:string; officePhone:string; website:string; license:string; licenseLabel?:string; red:string; dark:string; paper:string; font:string; logo:string; portrait?:string};
 scenes:CampaignScene[];
 captions:{start:number;end:number;text:string}[];
 audio?:string; music?:string;
 map?:{roads:number[][][]; markers:{x:number;y:number;label:string}[];attribution:string; caption?:string};
};
