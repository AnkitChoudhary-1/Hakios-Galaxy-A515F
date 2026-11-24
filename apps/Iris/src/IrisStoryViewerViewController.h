// IrisStoryViewerViewController.h
#import <UIKit/UIKit.h>
#import "IrisData.h"

@interface IrisStoryViewerViewController : UIViewController

@property (nonatomic, strong, readonly) IrisStory *story;

- (instancetype)initWithStory:(IrisStory *)story;

@end
